from jobs.models import Application, Resume
from jobs.tasks import process_resume
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from applicants.auth import IsApplicant, generate_applicant_tokens
from applicants.models import Applicant
from applicants.serializers import (
    ApplicantApplicationSerializer,
    ApplicantLoginSerializer,
    ApplicantResumeSerializer,
    ApplicantSerializer,
    ApplicantSignupSerializer,
)


def associate_guest_applications(applicant: Applicant):
    """
    Links any existing guest applications (and their associated resumes)
    submitted with this applicant's email address to their account.
    """
    guest_apps = Application.objects.filter(
        applicant__isnull=True,
        guest_email__iexact=applicant.email,
    )
    if guest_apps.exists():
        resume_ids = list(guest_apps.values_list("resume_id", flat=True))
        Resume.objects.filter(id__in=resume_ids, applicant__isnull=True).update(applicant=applicant)
        guest_apps.update(applicant=applicant)


class ApplicantSignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ApplicantSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        applicant = serializer.save()

        # Link any guest applications submitted earlier with the same email
        associate_guest_applications(applicant)

        tokens = generate_applicant_tokens(applicant)
        return Response(
            {
                "applicant": ApplicantSerializer(applicant).data,
                "tokens": tokens,
            },
            status=status.HTTP_201_CREATED,
        )


class ApplicantLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ApplicantLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        applicant = serializer.validated_data["applicant"]

        # Link any guest applications submitted earlier with the same email
        associate_guest_applications(applicant)

        tokens = generate_applicant_tokens(applicant)
        return Response(
            {
                "applicant": ApplicantSerializer(applicant).data,
                "tokens": tokens,
            },
            status=status.HTTP_200_OK,
        )


class ApplicantProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ApplicantSerializer
    permission_classes = [IsApplicant]

    def get_object(self):
        return self.request.user


class ApplicantResumeListView(generics.ListCreateAPIView):
    serializer_class = ApplicantResumeSerializer
    permission_classes = [IsApplicant]

    def get_queryset(self):
        return Resume.objects.filter(applicant=self.request.user).order_by(
            "-created_at"
        )

    def perform_create(self, serializer):
        file_obj = self.request.FILES.get("file")
        original_filename = file_obj.name if file_obj else "resume.pdf"
        resume = serializer.save(
            applicant=self.request.user,
            original_filename=original_filename,
        )
        # Background text extraction, chunking, and embedding
        process_resume.delay_on_commit(resume.id)


class ApplicantApplicationListView(generics.ListAPIView):
    serializer_class = ApplicantApplicationSerializer
    permission_classes = [IsApplicant]

    def get_queryset(self):
        return (
            Application.objects.filter(applicant=self.request.user)
            .select_related("job", "job__company", "resume")
            .order_by("-created_at")
        )
