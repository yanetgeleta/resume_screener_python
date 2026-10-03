import hashlib
import json
import logging
from datetime import timedelta

import pymupdf
from accounts.models import Company
from applicants.auth import IsCompany
from applicants.models import Applicant
from asgiref.sync import sync_to_async
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import connection, models
from django.db.models.functions import Cast
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
from jobs.services.resume_hashing import hash_resume_text
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

logger = logging.getLogger(__name__)


# Create your views here.
class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer

    def get_permissions(self):
        if self.action in ["search", "apply", "retrieve", "list"]:
            return [permissions.AllowAny()]
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "recompute",
            "see_result",
        ]:
            return [IsCompany()]
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
        - Full-text search on title, description, skills (Postgres FTS).
        - Semantic vector similarity using MiniLM embedding vs Job.embedding.
        - Normalized blended score for ranking.
        - Graceful fallback to pure full-text search on embedding failure.
        """
        query = (
            request.query_params.get("q") or request.query_params.get("query") or ""
        ).strip()
        jobs_qs = Job.objects.filter(is_active=True).select_related("company")

        if not query:
            jobs_qs = jobs_qs.order_by("-created_at")
            serializer = self.get_serializer(jobs_qs, many=True)
            return Response(serializer.data)

        # 1. Full-text search (PostgreSQL FTS) with weighted fields
        if connection.vendor == "postgresql":
            search_vector = (
                SearchVector("title", weight="A", config="english")
                + SearchVector(
                    Cast("skills", models.TextField()), weight="B", config="english"
                )
                + SearchVector("description", weight="C", config="english")
            )
            try:
                search_query = SearchQuery(
                    query, config="english", search_type="websearch"
                ) | SearchQuery(query, config="english", search_type="plain")
            except Exception:
                search_query = SearchQuery(query, config="english")

            fts_matches = jobs_qs.annotate(
                search_vec=search_vector,
                search_rank=SearchRank(search_vector, search_query),
            ).filter(
                models.Q(search_vec=search_query)
                | models.Q(title__icontains=query)
                | models.Q(skills__icontains=query)
                | models.Q(description__icontains=query)
            )
        else:
            fts_matches = jobs_qs.filter(
                models.Q(title__icontains=query)
                | models.Q(skills__icontains=query)
                | models.Q(description__icontains=query)
            )

        # 2. Semantic vector similarity with Graceful Fallback
        query_vec = None
        try:
            query_vec = embed_text(query)
        except Exception as exc:
            logger.warning(
                "Embedding generation failed for search query '%s': %s. Falling back gracefully to full-text search.",
                query,
                exc,
            )
            query_vec = None

        # Fallback path if embedding model failed or is unavailable
        if query_vec is None:
            if connection.vendor == "postgresql":
                fallback_results = list(
                    fts_matches.order_by("-search_rank", "-created_at")
                )
            else:
                fallback_results = list(fts_matches.order_by("-created_at"))
            serializer = self.get_serializer(fallback_results, many=True)
            return Response(serializer.data)

        # 3. Vector similarity query
        annotated_jobs = []
        try:
            annotated_jobs = jobs_qs.exclude(embedding__isnull=True).annotate(
                semantic_dist=MaxInnerProduct("embedding", query_vec)
            )
        except Exception as exc:
            logger.warning(
                "Vector similarity query failed for search query '%s': %s. Falling back gracefully to full-text search.",
                query,
                exc,
            )
            if connection.vendor == "postgresql":
                fallback_results = list(
                    fts_matches.order_by("-search_rank", "-created_at")
                )
            else:
                fallback_results = list(fts_matches.order_by("-created_at"))
            serializer = self.get_serializer(fallback_results, many=True)
            return Response(serializer.data)

        # 4. Blend FTS relevance and semantic similarity
        text_matches_dict = {}
        max_rank = 0.0
        for j in fts_matches:
            rank = getattr(j, "search_rank", None) or 0.0
            max_rank = max(max_rank, rank)
            text_matches_dict[j.id] = (rank, j)

        def get_t_score(job_id):
            if job_id not in text_matches_dict:
                return 0.0
            rank, _ = text_matches_dict[job_id]
            if max_rank > 0 and rank > 0:
                return 0.5 + 0.5 * (rank / max_rank)
            return 0.5

        semantic_map = {}
        for aj in annotated_jobs:
            sem_sim = -aj.semantic_dist  # convert inner product dist back to similarity
            semantic_map[aj.id] = (sem_sim, aj)

        CUTOFF_SEMANTIC_SIMILARITY = 0.30
        candidate_ids = set(text_matches_dict.keys()) | {
            jid
            for jid, (sim, _) in semantic_map.items()
            if sim >= CUTOFF_SEMANTIC_SIMILARITY
        }

        ranked_jobs = []
        for j_id in candidate_ids:
            t_score = get_t_score(j_id)
            if j_id in semantic_map:
                sem_sim, job_obj = semantic_map[j_id]
                norm_sem = max(0.0, min(1.0, (sem_sim + 1.0) / 2.0))
            else:
                sem_sim = 0.0
                norm_sem = 0.0
                job_obj = text_matches_dict[j_id][1]

            blended_score = (0.5 * t_score) + (0.5 * norm_sem)
            if j_id in text_matches_dict or sem_sim >= CUTOFF_SEMANTIC_SIMILARITY:
                ranked_jobs.append((blended_score, t_score, job_obj))

        ranked_jobs.sort(key=lambda x: (x[0], x[1]), reverse=True)
        results = [j for _, _, j in ranked_jobs]
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
                if not is_applicant:
                    if not file_obj:
                        return Response(
                            {"error": "Resume PDF file is required."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
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
            file_bytes = file_obj.read()
            file_obj.seek(0)
            with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
                raw_text = "".join(page.get_text() for page in doc)
                content_hash = hash_resume_text(raw_text)
            resume = None
            if is_applicant:
                resume = Resume.objects.filter(
                    applicant=user, content_hash=content_hash
                ).first()
            if not resume or not is_applicant:
                resume = Resume.objects.create(
                    original_filename=file_obj.name,
                    file=file_obj,
                    applicant=user if is_applicant else None,
                    company=None,
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
        if not request.user.is_staff and (
            not isinstance(request.user, Company) or job.company_id != request.user.id
        ):
            return Response(
                {"error": "Permission denied for this job."},
                status=status.HTTP_403_FORBIDDEN,
            )

        has_processed = job.applications.filter(
            pipeline_status=Application.PipelineStatus.PROCESSED
        ).exists()
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
    permission_classes = [permissions.IsAuthenticated, IsCompany]
    parser_classes = [FormParser, MultiPartParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Resume.objects.all()
        return Resume.objects.filter(company=user)

    def create(self, request, *args, **kwargs):
        """
        Accepts single file uploads ('file') or batch/folder uploads ('files' or multiple 'file'). Processes resumes, makes an application for each resume uploaded.
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

        existing_hashes = set(
            Resume.objects.filter(
                company=request.user, content_hash__isnull=False
            ).values_list("content_hash", flat=True)
        )

        resumes_to_link = []
        new_payload = []

        for file_obj in uploaded_files:
            file_bytes = file_obj.read()
            file_obj.seek(0)

            content_hash = hashlib.sha256(file_bytes).hexdigest()

            if content_hash and content_hash in existing_hashes:
                exisiting_resume = Resume.objects.filter(
                    company=self.request.user, content_hash=content_hash
                ).first()
                if exisiting_resume:
                    resumes_to_link.append(exisiting_resume)
                    continue
            new_payload.append(
                {
                    "file": file_obj,
                    "original_filename": file_obj.name,
                }
            )
        if new_payload:
            serializer = self.get_serializer(data=new_payload, many=True)
            serializer.is_valid(raise_exception=True)
            created_resumes = serializer.save(company=request.user)

            for resume in created_resumes:
                process_resume.delay_on_commit(resume.id)
                resumes_to_link.append(resume)

        job_id = (
            request.data.get("job")
            or request.data.get("job_id")
            or request.query_params.get("job_id")
        )
        # There must be a job id, because you can't bulk apply without creating a job first
        if job_id:
            try:
                job = Job.objects.get(id=job_id)
                if not request.user.is_staff and job.company_id != request.user.id:
                    return Response(
                        {"error": "Permission denied for this job."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                for resume in resumes_to_link:
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
        response_serializer = self.get_serializer(resumes_to_link, many=True)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompany]

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
    permission_classes = [permissions.IsAuthenticated, IsCompany]

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

    if not user.is_staff and (
        not isinstance(user, Company) or session.company_id != user.id
    ):
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

    # Immediately return the stream; defer heavy retrieval & persistence inside generator
    async def chat_sse_event_stream():
        accumulated_text = ""
        saved = False

        try:
            # 1. Immediate handshake packet to establish connection & cut TTFT to <50ms
            yield f"data: {json.dumps({'content': ''})}\n\n"

            # 2. Persist incoming user query in background inside stream
            await ChatMessage.objects.acreate(
                session=session,
                role=ChatMessage.Role.USER,
                content=query,
            )

            # 3. Context & Multi-candidate resolution
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
                    extra_context = await sync_to_async(
                        format_ranked_candidates_context
                    )(scored_apps)

            # 4. Retrieval & Routing (Resolves Finding 13: skip vector search if extra_context is present)
            if extra_context:
                chunks = []
                band = "confident"
            else:
                chunks = await sync_to_async(fetch_candidate_chunks_for_session)(
                    session, query
                )
                band = get_confidence_band(chunks)

            # 5. Fast-path: Canned decline if out of scope
            if band == "decline":
                yield f"data: {json.dumps({'content': CANNED_DECLINE})}\n\n"
                yield "data: [DONE]\n\n"
                await ChatMessage.objects.acreate(
                    session=session,
                    role=ChatMessage.Role.ASSISTANT,
                    content=CANNED_DECLINE,
                )
                return

            # 6. Build prompt payload
            caution = CAUTION_CLAUSE if band == "borderline" else None
            messages = await sync_to_async(build_chat_prompt_messages)(
                session=session,
                query=query,
                chunks=chunks,
                caution_clause=caution,
                extra_context=extra_context,
            )

            # 7. Stream LLM tokens from Groq
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
            yield f"data: {json.dumps({'error': 'Failed to generate complete response.', 'detail': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

        finally:
            if not saved and accumulated_text.strip():
                await ChatMessage.objects.acreate(
                    session=session,
                    role=ChatMessage.Role.ASSISTANT,
                    content=accumulated_text,
                )
                saved = True

    response = StreamingHttpResponse(
        chat_sse_event_stream(), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
