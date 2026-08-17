from rest_framework import serializers

from .models import Application, Job


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "description",
            "required_experience_years",
            "skills",
            "company",
            "created_at",
            "is_active",
        ]
        read_only_fields = ["company", "id", "created_at"]


class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = resume


class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = [
            "id",
            "job",
            "resume",
            "status",
            "llm_profile",
            "final_score",
            "created_at",
        ]
