from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from pgvector.django import HnswIndex, VectorField

# Create your models here.


class Job(models.Model):
    class RankingStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not Started"
        COMPUTING = "computing", "Computing"
        RETRIEVAL_DONE = "retrieval_done", "Retrieval Done"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    ranking_status = models.CharField(
        max_length=20,
        choices=RankingStatus.choices,
        default=RankingStatus.NOT_STARTED,
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    required_experience_years = models.IntegerField(blank=True, null=True)
    skills = models.JSONField(default=None, blank=True, null=True)
    head_count = models.IntegerField(blank=True, null=True)
    embedding = VectorField(dimensions=384, blank=True, null=True)
    company = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["created_at"]


class Resume(models.Model):
    class Status(models.TextChoices):
        PENDING = "PE", _("PENDING")
        PROCESSING = "PR", _("PROCESSING")
        DONE = "D", _("DONE")
        FAILED = "F", _("FAILED")

    original_filename = models.CharField(max_length=200, blank=True, null=True)
    file = models.FileField()
    skills = models.JSONField(default=None, blank=True, null=True)
    experience_years = models.IntegerField(null=True, blank=True)
    full_text = models.TextField(blank=True, null=True)
    content_hash = models.CharField(max_length=64, db_index=True, null=True, blank=True)
    company = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resumes",
        null=True,
        blank=True,
    )
    applicant = models.ForeignKey(
        "applicants.Applicant",
        on_delete=models.SET_NULL,
        related_name="resumes",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=2, choices=Status, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(company__isnull=False, applicant__isnull=True)
                | models.Q(company__isnull=True, applicant__isnull=False),
                name="resume_exactly_one_of_company_or_applicant",
            )
        ]


class Application(models.Model):
    class Status(models.TextChoices):
        SHORTLISTED = "SL", _("SHORTLISTED")
        NORMAL = "N", _("NORMAL")

    class Source(models.TextChoices):
        COMPANY_UPLOAD = "company_upload", _("Company Upload")
        APPLICANT_SUBMITTED = "applicant_submitted", _("Applicant Submitted")

    class PipelineStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        PROCESSING = "processing", _("Processing")
        PROCESSED = "processed", _("Processed")
        FAILED = "failed", _("Failed")

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    resume = models.ForeignKey(
        Resume, on_delete=models.CASCADE, related_name="applications"
    )
    applicant = models.ForeignKey(
        "applicants.Applicant",
        on_delete=models.SET_NULL,
        related_name="applications",
        null=True,
        blank=True,
    )
    source = models.CharField(
        max_length=30,
        choices=Source.choices,
        default=Source.COMPANY_UPLOAD,
    )
    pipeline_status = models.CharField(
        max_length=20,
        choices=PipelineStatus.choices,
        default=PipelineStatus.PENDING,
    )
    # Guest applicant fallback details
    guest_full_name = models.CharField(max_length=200, blank=True, null=True)
    guest_email = models.EmailField(blank=True, null=True)
    guest_phone_number = models.CharField(max_length=50, blank=True, null=True)

    retrieval_score = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=2, choices=Status, default=Status.NORMAL)
    llm_profile = models.JSONField(default=None, blank=True, null=True)
    final_score = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "resume"], name="unique_job_resume")
        ]


class JobApplicationField(models.Model):
    """
    Dynamic per-job custom questions configured by recruiters.
    """

    class FieldType(models.TextChoices):
        TEXT = "text", _("Text")
        TEXTAREA = "textarea", _("Textarea")
        NUMBER = "number", _("Number")
        BOOLEAN = "boolean", _("Boolean")
        SINGLE_CHOICE = "single_choice", _("Single Choice")

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="application_fields",
    )
    label = models.CharField(max_length=255)
    field_type = models.CharField(
        max_length=20,
        choices=FieldType.choices,
        default=FieldType.TEXT,
    )
    choices = models.JSONField(
        default=list,
        blank=True,
        help_text="Options for single_choice field types",
    )
    required = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.job.title} - {self.label} ({self.field_type})"


class ApplicationAnswer(models.Model):
    """
    Applicant responses to dynamic JobApplicationFields.
    """

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    field = models.ForeignKey(
        JobApplicationField,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    value = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["field__order", "id"]

    def __str__(self):
        return f"App {self.application_id} - {self.field.label}: {self.value[:30]}"


class ResumeChunk(models.Model):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="chunks")
    chunk_text = models.TextField()
    embedding = VectorField(
        dimensions=384,
    )
    chunk_index = models.PositiveIntegerField(
        help_text="Order index of the chunk within the resume"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["chunk_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["resume", "chunk_index"], name="unique_resume_chunk_index"
            )
        ]
        indexes = [
            HnswIndex(
                name="resume_chunk_embedding_hnsw_idx",
                fields=["embedding"],
                m=16,  # max connections per element (default 16)
                ef_construction=64,  # size of dynamic candidate list (default 64)
                opclasses=["vector_ip_ops"],
            )
        ]

    def __str__(self) -> str:
        return f"Resume {self.resume} Chunk {self.chunk_index}"


class ChatSession(models.Model):
    """
    Groups RAG conversation around a specific Job and Tenant.
    """

    company = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="chat_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["company", "job"]),
        ]

    def __str__(self):
        return f"ChatSession {self.id} (Job: {self.job_id}, Company: {self.company_id})"


class ChatMessage(models.Model):
    """
    Individual messages within a ChatSession.
    """

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER,
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
        ]

    def __str__(self):
        return f"[{self.role}] {self.content[:30]}..."
