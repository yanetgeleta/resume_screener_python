from jobs.models import Application, Resume
from jobs.tasks import process_resume
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from applicants.auth import IsApplicant, generate_applicant_tokens
from applicants.serializers import (
    ApplicantApplicationSerializer,
    ApplicantLoginSerializer,
    ApplicantResumeSerializer,
    ApplicantSerializer,
    ApplicantSignupSerializer,
)


class ApplicantSignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ApplicantSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        applicant = serializer.save()

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
