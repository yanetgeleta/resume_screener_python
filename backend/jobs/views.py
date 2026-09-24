import json
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from jobs.groq_client import async_groq_client_instance
from jobs.services.chat import (
    CANNED_DECLINE,
    CAUTION_CLAUSE,
    GROQ_CHAT_MODEL,
    build_chat_prompt_messages,
    format_ranked_candidates_context,
    get_confidence_band,
)
from jobs.services.retrieval import fetch_candidate_chunks_for_session
from jobs.tasks import (
    embed_job,
    extract_job_profile,
    process_resume,
    recompute_job_rankings,
)

from .models import Application, ChatMessage, ChatSession, Job, Resume
from .serializers import (
    ApplicationSerializer,
    ChatMessageSerializer,
    ChatSessionSerializer,
    JobSerializer,
    ResumeSerializer,
)


# Create your views here.
class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Job.objects.all()
        return Job.objects.filter(company=user)

    def perform_create(self, serializer):
        created_job = serializer.save(company=self.request.user)
        embed_job.delay_on_commit(created_job.id)
        extract_job_profile.delay_on_commit(created_job.id)

    @action(detail=True, methods=["post"])
    def recompute(self, request, pk=None):
        job = self.get_object()
        job.ranking_status = Job.RankingStatus.COMPUTING
        job.save(update_fields=["ranking_status"])
        recompute_job_rankings.delay_on_commit(job.id)
        return Response(
            {
                "detail": "Ranking recomputation started.",
                "ranking_status": job.ranking_status,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ResumeViewSet(viewsets.ModelViewSet):
    serializer_class = ResumeSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [FormParser, MultiPartParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Resume.objects.all()
        return Resume.objects.filter(company=user)

    def create(self, request, *args, **kwargs):
        """
        Accepts single file uploads ('file') or batch/folder uploads ('files' or multiple 'file').
        """
        # Collect all files whether the key is 'files' or 'file'
        uploaded_files = request.FILES.getlist("files") or request.FILES.getlist("file")

        if not uploaded_files:
            return Response(
                {
                    "error": "No files provided. Send file(s) under the key 'files' or 'file'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = [
            {
                "file": file_obj,
                "original_filename": file_obj.name,
            }
            for file_obj in uploaded_files
        ]

        # 1. Run all items through DRF Validation (validate_file, required fields, etc.)
        serializer = self.get_serializer(data=payload, many=True)
        serializer.is_valid(raise_exception=True)

        # 2. Save through standard DRF/ORM save() pipeline (fires storage & signals)
        created_resumes = serializer.save(company=request.user)
        for resume in created_resumes:
            process_resume.delay_on_commit(resume.id)

        job_id = (
            request.data.get("job")
            or request.data.get("job_id")
            or request.query_params.get("job_id")
        )
        if job_id:
            try:
                job = Job.objects.get(id=job_id)
                if not request.user.is_staff and job.company_id != request.user.id:
                    return Response(
                        {"error": "Permission denied for this job."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                for resume in created_resumes:
                    Application.objects.get_or_create(job=job, resume=resume)
                job.ranking_status = Job.RankingStatus.COMPUTING
                job.save(update_fields=["ranking_status"])
                recompute_job_rankings.delay_on_commit(job.id)
            except Job.DoesNotExist:
                return Response(
                    {"error": "Job not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        base_qs = Application.objects.select_related("job", "resume")
        if user.is_staff:
            return base_qs.all()
        return base_qs.filter(job__company=user)

    def perform_create(self, serializer):
        created_application = serializer.save()


class ChatSessionViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            qs = ChatSession.objects.all()
        else:
            qs = ChatSession.objects.filter(company=user)

        job_id = self.request.query_params.get("job") or self.request.query_params.get(
            "job_id"
        )
        if job_id:
            qs = qs.filter(job_id=job_id)

        return qs.select_related("job", "company")

    def perform_create(self, serializer):
        serializer.save(company=self.request.user)

    def create(self, request, *args, **kwargs):
        # Prevent rapid duplicate session creation for the same job and user
        job_id = request.data.get("job") or request.data.get("job_id")
        if job_id and request.user.is_authenticated:
            recent_threshold = timezone.now() - timedelta(seconds=15)
            # Find if an empty session (no messages) was created very recently for this company and job
            recent_empty_session = (
                ChatSession.objects.filter(
                    company=request.user,
                    job_id=job_id,
                    created_at__gte=recent_threshold,
                    messages__isnull=True,
                )
                .order_by("-created_at")
                .first()
            )
            if recent_empty_session:
                serializer = self.get_serializer(recent_empty_session)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        """
        Sub-endpoint to load message history for this session on session open:
        GET /api/sessions/<id>/messages/
        Supports pagination if configured, or returns all messages chronologically.
        """
        session = self.get_object()
        messages_qs = session.messages.all().order_by("created_at")

        page = self.paginate_queryset(messages_qs)
        if page is not None:
            serializer = ChatMessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ChatMessageSerializer(messages_qs, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Step 6 — Groq Streaming Call → SSE Relay → Persist
# ---------------------------------------------------------------------------
async def _authenticate_user_for_stream(request):
    """Authenticate request using DRF's JWTAuthentication or existing request.user."""
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return user

    auth = JWTAuthentication()
    try:
        user_auth = await sync_to_async(auth.authenticate)(request)
        if user_auth:
            return user_auth[0]
    except Exception:
        pass
    return None


@csrf_exempt
async def chat_stream_view(request, session_id: int, job_id: int | None = None):
    """
    Async streaming view returning StreamingHttpResponse (text/event-stream):
    - Authenticates user and verifies tenant ownership of session.
    - Supports single candidate RAG as well as multi-candidate ranking summary synthesis.
    - Runs Step 3 retrieval & Step 4 similarity pre-filter.
    - Persists user ChatMessage.
    - Relays AsyncGroq token deltas as SSE data events.
    - Persists assistant ChatMessage upon completion or on client disconnect (partial).
    """
    user = await _authenticate_user_for_stream(request)
    if not user:
        return JsonResponse(
            {"detail": "Authentication credentials were not provided."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        session = await ChatSession.objects.select_related("job", "company").aget(
            id=session_id
        )
    except ChatSession.DoesNotExist:
        return JsonResponse(
            {"error": "Chat session not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not user.is_staff and session.company_id != user.id:
        return JsonResponse(
            {"error": "Permission denied for this chat session."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if job_id is not None and session.job_id != int(job_id):
        return JsonResponse(
            {"error": "Session does not belong to the specified job."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8")) if request.body else {}
            query = body.get("query") or body.get("message")
        except (json.JSONDecodeError, UnicodeDecodeError):
            query = request.POST.get("query") or request.POST.get("message")

    if not query or not query.strip():
        return JsonResponse(
            {"error": "A non-empty 'query' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    query = query.strip()

    # Check for multi-candidate profile/ranking summary query
    is_multi_candidate = any(
        kw in query.lower()
        for kw in [
            "top",
            "rank",
            "final_score",
            "final score",
            "candidate profile",
            "candidate profiles",
            "strengths, summary, and gaps",
            "summary, and gaps",
            "head_count",
            "best candidates",
            "shortlist",
            "shortlisted",
            "overview of candidates",
            "rankings",
        ]
    )

    extra_context = None
    if is_multi_candidate:
        head_count = getattr(session.job, "head_count", None) or 5
        scored_apps = await sync_to_async(list)(
            Application.objects.filter(
                job_id=session.job_id,
                final_score__isnull=False,
            )
            .select_related("resume")
            .order_by("-final_score")[:head_count]
        )
        if scored_apps:
            extra_context = format_ranked_candidates_context(scored_apps)

    # 1. Step 3: Candidate retrieval
    chunks = await sync_to_async(fetch_candidate_chunks_for_session)(session, query)

    # 2. Step 4 & Step 7: Deterministic routing based on top result distance
    if extra_context:
        band = "confident"
    else:
        band = get_confidence_band(chunks)

    # 3. If out of scope: return canned decline stream without calling Groq
    if band == "decline":
        await ChatMessage.objects.acreate(
            session=session,
            role=ChatMessage.Role.USER,
            content=query,
        )

        async def canned_sse_generator():
            yield f"data: {json.dumps({'content': CANNED_DECLINE})}\n\n"
            yield "data: [DONE]\n\n"
            await ChatMessage.objects.acreate(
                session=session,
                role=ChatMessage.Role.ASSISTANT,
                content=CANNED_DECLINE,
            )

        response = StreamingHttpResponse(
            canned_sse_generator(), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    # 4. Step 5 & 7: Build messages payload (caution clause injected if borderline)
    caution = CAUTION_CLAUSE if band == "borderline" else None
    messages = await sync_to_async(build_chat_prompt_messages)(
        session=session,
        query=query,
        chunks=chunks,
        caution_clause=caution,
        extra_context=extra_context,
    )

    # 5. Persist incoming user query before streaming response
    await ChatMessage.objects.acreate(
        session=session,
        role=ChatMessage.Role.USER,
        content=query,
    )

    # 6. Step 6: Relay token stream from AsyncGroq (openai/gpt-oss-120b)
    async def groq_sse_generator():
        accumulated_text = ""
        saved = False
        try:
            client = async_groq_client_instance
            stream = await client.chat.completions.create(
                model=GROQ_CHAT_MODEL,
                messages=messages,
                stream=True,
                temperature=0.2,
            )
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        accumulated_text += delta
                        yield f"data: {json.dumps({'content': delta})}\n\n"

            yield "data: [DONE]\n\n"

            if accumulated_text.strip():
                await ChatMessage.objects.acreate(
                    session=session,
                    role=ChatMessage.Role.ASSISTANT,
                    content=accumulated_text,
                )
                saved = True
        except Exception as exc:
            error_payload = {
                "error": "Failed to generate complete response from model.",
                "detail": str(exc),
            }
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            # Client disconnect / dropped stream:
            # Persist partial content so dialogue turns remain paired and context is not lost
            if not saved and accumulated_text.strip():
                await ChatMessage.objects.acreate(
                    session=session,
                    role=ChatMessage.Role.ASSISTANT,
                    content=accumulated_text,
                )
                saved = True

    response = StreamingHttpResponse(
        groq_sse_generator(), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
