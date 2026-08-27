from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from pgvector.django import HnswIndex, VectorField

# Create your models here.


class Job(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    required_experience_years = models.IntegerField(blank=True, null=True)
    skills = models.JSONField(default=dict, blank=True, null=True)
    head_count = models.IntegerField()
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
    skills = models.JSONField(default=dict, blank=True, null=True)
    experience_years = models.IntegerField(null=True, blank=True)
    company = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resumes"
    )
    status = models.CharField(max_length=2, choices=Status, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Application(models.Model):
    class Status(models.TextChoices):
        SHORTLISTED = "SL", _("SHORTLISTED")
        NORMAL = "N", _("NORMAL")

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    resume = models.ForeignKey(
        Resume, on_delete=models.CASCADE, related_name="applications"
    )
    status = models.CharField(max_length=2, choices=Status, default=Status.NORMAL)
    llm_profile = models.JSONField(default=dict, blank=True, null=True)
    final_score = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "resume"], name="unique_job_resume")
        ]


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
                opclasses=[
                    "vector_l2_ops"
                ],  # or "vector_cosine_ops" for cosine distance
            )
        ]

    def __str__(self) -> str:
        return f"Resume {self.resume} Chunk {self.chunk_index}"
