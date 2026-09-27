from django.contrib.auth.password_validation import validate_password
from jobs.models import Application, Job, Resume
from rest_framework import serializers

from applicants.models import Applicant


class ApplicantSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )

    class Meta:
        model = Applicant
        fields = ("id", "email", "full_name", "phone_number", "password", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_phone_number(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Phone number is required.")
        return value.strip()

    def create(self, validated_data):
        password = validated_data.pop("password")
        applicant = Applicant(**validated_data)
        applicant.set_password(password)
        applicant.save()
        return applicant


class ApplicantLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        try:
            applicant = Applicant.objects.get(email__iexact=email)
        except Applicant.DoesNotExist:
            raise serializers.ValidationError({"detail": "Invalid email or password."})

        if not applicant.is_active:
            raise serializers.ValidationError({"detail": "This account is inactive."})

        if not applicant.check_password(password):
            raise serializers.ValidationError({"detail": "Invalid email or password."})

        attrs["applicant"] = applicant
        return attrs


class ApplicantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Applicant
        fields = ("id", "email", "full_name", "phone_number", "created_at")
        read_only_fields = ("id", "email", "created_at")


class ApplicantResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = (
            "id",
            "original_filename",
            "file",
            "skills",
            "experience_years",
            "created_at",
        )
        read_only_fields = ("id", "skills", "experience_years", "created_at")

    def validate_file(self, value):
        if not value.name.lower().endswith(".pdf"):
            raise serializers.ValidationError("Only PDF files are allowed.")
        max_size_mb = 10
        if value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(
                f"File size exceeds maximum allowed size ({max_size_mb}MB)."
            )
        return value


class JobMinimalSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.company_name", read_only=True)

    class Meta:
        model = Job
        fields = ("id", "title", "company_name", "created_at", "is_active")


class ApplicantApplicationSerializer(serializers.ModelSerializer):
    job = JobMinimalSerializer(read_only=True)
    resume_filename = serializers.CharField(
        source="resume.original_filename", read_only=True
    )

    class Meta:
        model = Application
        fields = (
            "id",
            "job",
            "resume",
            "resume_filename",
            "source",
            "pipeline_status",
            "status",
            "created_at",
        )
        read_only_fields = fields
