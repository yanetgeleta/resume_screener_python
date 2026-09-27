from rest_framework import serializers

from .models import (
    Application,
    ApplicationAnswer,
    ChatMessage,
    ChatSession,
    Job,
    JobApplicationField,
    Resume,
)


class JobApplicationFieldSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = JobApplicationField
        fields = [
            "id",
            "label",
            "field_type",
            "choices",
            "required",
            "order",
        ]


class ApplicationAnswerSerializer(serializers.ModelSerializer):
    field_label = serializers.CharField(source="field.label", read_only=True)
    field_type = serializers.CharField(source="field.field_type", read_only=True)

    class Meta:
        model = ApplicationAnswer
        fields = [
            "id",
            "field",
            "field_label",
            "field_type",
            "value",
        ]


class JobSerializer(serializers.ModelSerializer):
    application_fields = JobApplicationFieldSerializer(many=True, required=False)
    company_name = serializers.CharField(source="company.company_name", read_only=True)
    application_count = serializers.SerializerMethodField()
    processed_application_count = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "description",
            "required_experience_years",
            "skills",
            "head_count",
            "embedding",
            "ranking_status",
            "company",
            "company_name",
            "created_at",
            "is_active",
            "application_fields",
            "application_count",
            "processed_application_count",
        ]
        read_only_fields = [
            "company",
            "id",
            "created_at",
            "skills",
            "ranking_status",
            "company_name",
            "application_count",
            "processed_application_count",
        ]

    def get_application_count(self, obj):
        return obj.applications.count()

    def get_processed_application_count(self, obj):
        return obj.applications.filter(pipeline_status="processed").count()

    def create(self, validated_data):
        fields_data = validated_data.pop("application_fields", [])
        job = Job.objects.create(**validated_data)
        for idx, field_data in enumerate(fields_data):
            field_data.pop("id", None)
            if "order" not in field_data:
                field_data["order"] = idx
            JobApplicationField.objects.create(job=job, **field_data)
        return job

    def update(self, instance, validated_data):
        fields_data = validated_data.pop("application_fields", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if fields_data is not None:
            existing_field_ids = []
            for idx, field_data in enumerate(fields_data):
                field_id = field_data.get("id")
                clean_data = {k: v for k, v in field_data.items() if k != "id"}
                if "order" not in clean_data:
                    clean_data["order"] = idx
                if field_id:
                    JobApplicationField.objects.filter(id=field_id, job=instance).update(**clean_data)
                    existing_field_ids.append(field_id)
                else:
                    new_f = JobApplicationField.objects.create(job=instance, **clean_data)
                    existing_field_ids.append(new_f.id)
            instance.application_fields.exclude(id__in=existing_field_ids).delete()

        return instance


class ResumeSerializer(serializers.ModelSerializer):
    original_filename = serializers.CharField(max_length=200, required=True)

    class Meta:
        model = Resume
        fields = [
            "id",
            "original_filename",
            "file",
            "skills",
            "experience_years",
            "full_text",
            "company",
            "applicant",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "skills",
            "experience_years",
            "company",
            "applicant",
            "status",
            "created_at",
        ]

    def validate_file(self, value):
        """Makes sure only pdf files are accepted and they are not greater than 10MB"""
        if not value.name.lower().endswith(".pdf"):
            raise serializers.ValidationError("Only PDF files are allowed.")

        max_size_mb = 10
        if value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(
                f"File size exceeds maximum allowed size ({max_size_mb}MB)."
            )
        return value


class ApplicationSerializer(serializers.ModelSerializer):
    job = serializers.PrimaryKeyRelatedField(queryset=Job.objects.all())
    resume = serializers.PrimaryKeyRelatedField(queryset=Resume.objects.all())
    answers = ApplicationAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = Application
        fields = [
            "id",
            "job",
            "resume",
            "applicant",
            "source",
            "pipeline_status",
            "guest_full_name",
            "guest_email",
            "guest_phone_number",
            "status",
            "llm_profile",
            "retrieval_score",
            "final_score",
            "created_at",
            "answers",
        ]
        read_only_fields = [
            "id",
            "status",
            "llm_profile",
            "final_score",
            "created_at",
        ]

    def validate(self, attrs):
        """Validator: Makes sure company does only legal actions if authenticated"""
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return attrs
        current_company = request.user
        job = attrs.get("job") or getattr(self.instance, "job", None)
        resume = attrs.get("resume") or getattr(self.instance, "resume", None)

        # Skip company ownership check if user is staff or an applicant
        if not current_company.is_staff and hasattr(current_company, "company_name"):
            if job and job.company != current_company:
                raise serializers.ValidationError(
                    {
                        "job": "You cannot submit an application to a job posting owned by another company."
                    }
                )
            if resume and resume.company and resume.company != current_company:
                raise serializers.ValidationError(
                    {
                        "resume": "You cannot submit an application to a job with a resume owned by another company."
                    }
                )
        if job and not job.is_active:
            raise serializers.ValidationError(
                {"job": "You cannot create an application for inactive job posting."}
            )
        return attrs

    def to_representation(self, instance):
        """Nested Pattern: replaces the ids for job and resume with their information"""
        representation = super().to_representation(instance)
        representation["job"] = JobSerializer(instance.job, context=self.context).data
        representation["resume"] = ResumeSerializer(
            instance.resume, context=self.context
        ).data
        return representation


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "session",
            "role",
            "content",
            "created_at",
        ]
        read_only_fields = ["id", "session", "created_at"]


class ChatSessionSerializer(serializers.ModelSerializer):
    job = serializers.PrimaryKeyRelatedField(queryset=Job.objects.all())
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "job",
            "company",
            "messages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "messages",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return attrs

        user = request.user
        job = attrs.get("job") or getattr(self.instance, "job", None)

        if not user.is_staff and job and job.company != user:
            raise serializers.ValidationError(
                {"job": "You cannot create a chat session for a job owned by another company."}
            )

        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.job:
            representation["job_title"] = instance.job.title
        return representation
