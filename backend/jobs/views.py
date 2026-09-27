import json
from datetime import timedelta

from applicants.models import Applicant
from asgiref.sync import sync_to_async
from django.db import models
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from pgvector.django import MaxInnerProduct
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
from jobs.services.embedding import embed_text
from jobs.services.retrieval import fetch_candidate_chunks_for_session
from jobs.tasks import (
    embed_job,
    extract_job_profile,
    process_resume,
    process_single_application,
    recompute_job_rankings,
)

from .models import (
    Application,
    ApplicationAnswer,
    ChatMessage,
    ChatSession,
    Job,
    JobApplicationField,
    Resume,
)
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

    def get_permissions(self):
        if self.action in ["search", "apply", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Job.objects.filter(is_active=True).select_related("company")
        if isinstance(user, Applicant):
            return Job.objects.filter(is_active=True).select_related("company")
        if user.is_staff:
            return Job.objects.all().select_related("company")
        return Job.objects.filter(company=user).select_related("company")

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

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def search(self, request):
        """
        Public and authenticated job search endpoint:
        - Full-text match on title, description, skills.
        - Semantic vector similarity using MiniLM embedding vs Job.embedding.
        - Normalized blended score for ranking.
        """
        query = (
            request.query_params.get("q") or request.query_params.get("query") or ""
        ).strip()
        jobs_qs = Job.objects.filter(is_active=True).select_related("company")

        if not query:
            jobs_qs = jobs_qs.order_by("-created_at")
            serializer = self.get_serializer(jobs_qs, many=True)
            return Response(serializer.data)

        # 1. Text match filter (title, description, skills)
        text_matches = jobs_qs.filter(
            models.Q(title__icontains=query)
            | models.Q(description__icontains=query)
            | models.Q(skills__icontains=query)
        )
        text_match_ids = set(text_matches.values_list("id", flat=True))

        # 2. Semantic vector similarity
        query_vec = embed_text(query)
        annotated_jobs = jobs_qs.exclude(embedding__isnull=True).annotate(
            semantic_dist=MaxInnerProduct("embedding", query_vec)
        )

        job_scores = {}
        for j in jobs_qs:
            t_score = 1.0 if j.id in text_match_ids else 0.0
            job_scores[j.id] = (t_score, 0.0, j)
        # This goes through the annotated jobs and adds the semantic similarity to them. If not it will assign them 0 and reassigns
        for aj in annotated_jobs:
            t_score, _, j = job_scores.get(aj.id, (0.0, 0.0, aj))
            sem_sim = -aj.semantic_dist  # convert inner product dist back to similarity
            job_scores[aj.id] = (t_score, sem_sim, aj)

        # Blend: 0.5 text + 0.5 normalized semantic
        ranked_jobs = []
        for j_id, (t_score, sem_sim, job_obj) in job_scores.items():
            norm_sem = max(0.0, min(1.0, (sem_sim + 1.0) / 2.0))
            blended_score = (0.5 * t_score) + (0.5 * norm_sem)
            if blended_score > 0.05 or j_id in text_match_ids:
                ranked_jobs.append((blended_score, job_obj))

        ranked_jobs.sort(key=lambda x: x[0], reverse=True)
        results = [j for _, j in ranked_jobs]
        serializer = self.get_serializer(results, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.AllowAny],
        parser_classes=[FormParser, MultiPartParser, JSONParser],
    )
    def apply(self, request, pk=None):
        """
        Job apply endpoint for authenticated applicants and guests:
        - Authenticated applicant: can choose existing resume or upload a new one.
        - Guest: captures full_name, email, phone_number directly on application and requires PDF upload.
        - Dynamic custom fields (JobApplicationField) submitted as answers.
        - Dispatches unified single-application pipeline in the background and returns immediate confirmation.
        """
        job = self.get_object()
        if not job.is_active:
            return Response(
                {"error": "This job posting is inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = (
            request.user if (request.user and request.user.is_authenticated) else None
        )
        is_applicant = isinstance(user, Applicant)

        resume_id = request.data.get("resume_id") or request.data.get("resume")
        file_obj = request.FILES.get("file") or request.FILES.get("resume")

        guest_name = request.data.get("full_name") or request.data.get("name")
        guest_email = request.data.get("email")
        guest_phone = request.data.get("phone_number") or request.data.get("phone")

        if not is_applicant:
            if not guest_name or not str(guest_name).strip():
                return Response(
                    {"error": "Full name is required for guest application."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not guest_email or not str(guest_email).strip():
                return Response(
                    {"error": "Email is required for guest application."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not guest_phone or not str(guest_phone).strip():
                return Response(
                    {"error": "Phone number is required for guest application."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not file_obj:
                return Response(
                    {"error": "Resume PDF file is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        resume = None
        if resume_id:
            try:
                if is_applicant:
                    resume = Resume.objects.get(id=resume_id, applicant=user)
                else:
                    resume = Resume.objects.get(id=resume_id)
            except Resume.DoesNotExist:
                return Response(
                    {"error": "Specified resume was not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        elif file_obj:
            if not file_obj.name.lower().endswith(".pdf"):
                return Response(
                    {"error": "Only PDF files are allowed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            resume = Resume.objects.create(
                original_filename=file_obj.name,
                file=file_obj,
                applicant=user if is_applicant else None,
                company=job.company,
            )
        else:
            return Response(
                {"error": "Either resume_id or a resume PDF file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse and validate dynamic field answers
        req_fields = job.application_fields.filter(required=True)
        raw_answers = request.data.get("answers")
        answers_dict = {}
        if isinstance(raw_answers, str):
            try:
                raw_answers = json.loads(raw_answers)
            except Exception:
                raw_answers = []
        if isinstance(raw_answers, list):
            for ans in raw_answers:
                if isinstance(ans, dict) and "field_id" in ans:
                    answers_dict[int(ans["field_id"])] = str(ans.get("value", ""))
                elif isinstance(ans, dict) and "field" in ans:
                    answers_dict[int(ans["field"])] = str(ans.get("value", ""))
        for key, val in request.data.items():
            if key.startswith("field_"):
                try:
                    f_id = int(key.replace("field_", ""))
                    answers_dict[f_id] = str(val)
                except ValueError:
                    pass

        for rf in req_fields:
            if rf.id not in answers_dict or not answers_dict[rf.id].strip():
                return Response(
                    {"error": f"Application question '{rf.label}' is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        application, created = Application.objects.get_or_create(
            job=job,
            resume=resume,
            defaults={
                "applicant": user if is_applicant else None,
                "source": Application.Source.APPLICANT_SUBMITTED,
                "pipeline_status": Application.PipelineStatus.PENDING,
                "guest_full_name": str(guest_name).strip()
                if not is_applicant and guest_name
                else None,
                "guest_email": str(guest_email).strip()
                if not is_applicant and guest_email
                else None,
                "guest_phone_number": str(guest_phone).strip()
                if not is_applicant and guest_phone
                else None,
            },
        )
        if not created:
            application.source = Application.Source.APPLICANT_SUBMITTED
            application.pipeline_status = Application.PipelineStatus.PENDING
            application.save(update_fields=["source", "pipeline_status"])

        for field_id, value in answers_dict.items():
            try:
                field_obj = job.application_fields.get(id=field_id)
                ApplicationAnswer.objects.update_or_create(
                    application=application,
                    field=field_obj,
                    defaults={"value": value},
                )
            except JobApplicationField.DoesNotExist:
                pass

        # Dispatch background pipeline for this single application!
        process_single_application.delay_on_commit(application.id)

        return Response(
            {
                "status": "submitted",
                "application_id": application.id,
                "pipeline_status": application.pipeline_status,
                "message": "Application submitted successfully.",
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="see-result")
    def see_result(self, request, pk=None):
        """
        Lightweight 'See result' endpoint:
        - Accessible once the job has >= 1 Application with pipeline_status=processed.
        - Creates or retrieves the job's ChatSession.
        - Returns session_id for immediate navigation without wait-states.
        """
        job = self.get_object()
        if not request.user.is_staff and job.company_id != request.user.id:
            return Response(
                {"error": "Permission denied for this job."},
                status=status.HTTP_403_FORBIDDEN,
            )

        has_processed = (
            job.applications.filter(
                pipeline_status=Application.PipelineStatus.PROCESSED
            ).count()
            >= job.head_count
        )
        if not has_processed:
            return Response(
                {
                    "error": "No processed applications available yet for this job.",
                    "detail": "At least one candidate application must have completed processing.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        session, created = ChatSession.objects.get_or_create(
            company=request.user,
            job=job,
        )
        return Response(
            {
                "session_id": session.id,
                "created": created,
                "has_messages": session.messages.exists(),
                "job_id": job.id,
                "job_title": job.title,
            },
            status=status.HTTP_200_OK,
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
                    Application.objects.get_or_create(
                        job=job,
                        resume=resume,
                        defaults={
                            "source": Application.Source.COMPANY_UPLOAD,
                            "pipeline_status": Application.PipelineStatus.PENDING,
                        },
                    )
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

    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed. Use POST."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

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
            extra_context = await sync_to_async(format_ranked_candidates_context)(
                scored_apps
            )

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
