from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from jobs.tasks import embed_job, process_resume, recompute_job_rankings

from .models import Application, Job, Resume
from .serializers import ApplicationSerializer, JobSerializer, ResumeSerializer


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
