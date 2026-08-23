from rest_framework import serializers

from .models import Application, Job, Resume


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
        read_only_fields = ["company", "id", "created_at", "skills"]


class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = [
            "id",
            "original_filename",
            "file",
            "uploaded_at",
            "skills",
            "experience_years",
            "company",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "uploaded_at",
            "skills",
            "experience_years",
            "company",
            "created_at",
        ]


class ApplicationSerializer(serializers.ModelSerializer):
    job = serializers.PrimaryKeyRelatedField(queryset=Job.objects.all())
    resume = serializers.PrimaryKeyRelatedField(queryset=Resume.objects.all())

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
        read_only_fields = [
            "id",
            "status",
            "llm_profile",
            "final_score",
            "created_at",
        ]

        def validate(self, attrs):
            request = self.context.get("request")
            if not request or not request.user or not request.user.is_authenticated:
                return attrs
            current_company = request.user
            job = attrs.get("job") or getattr(self.instance, "resume", None)
            resume = attrs.get("resume") or getattr(self.instance, "resume", None)

            if not current_company.is_staff:
                if job and job.company != current_company:
                    raise serializers.ValidationError(
                        {
                            "job": "You cannot submit an application to a job posting owned by another company."
                        }
                    )
                if resume and resume.company != current_company:
                    raise serializers.ValidationError(
                        {
                            "resume": "You cannot submit an application to a job with a resume owned by another company."
                        }
                    )
            if job and not job.is_active:
                raise serializers.ValidationError(
                    {
                        "job": "You cannot create an application for inactive job posting."
                    }
                )
            return attrs

        def to_representation(self, instance):
            representation = super().to_representation(instance)
            representation["job"] = JobSerializer(
                instance.job, context=self.context
            ).data
            representation["resume"] = ResumeSerializer(
                instance.resume, context=self.context
            ).data
            return representation
