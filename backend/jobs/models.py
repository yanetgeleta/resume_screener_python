from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.


class Job(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    required_experience_years = models.IntegerField()
    skills = models.JSONField(default=dict, blank=True, null=True)
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

    original_filename = models.CharField(max_length=200, blank=True, null=True)
    file = models.FileField()
    skills = models.JSONField(default=dict, blank=True, null=True)
    experience_years = models.IntegerField(null=True, blank=True)
    company = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resumes"
    )
    # status
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
