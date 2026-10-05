import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class Applicant(models.Model):
    """
    Applicant entity — decoupled from AUTH_USER_MODEL (Company).
    Uses Argon2/standard Django password hashing and parallel JWT auth.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # id = models.CharField(primary_key=True, max_length=50)
    email = models.EmailField(unique=True, null=False, blank=False)
    password = models.CharField(max_length=255)
    full_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    def set_password(self, raw_password: str):
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    @property
    def is_staff(self) -> bool:
        return False

    @property
    def is_superuser(self) -> bool:
        return False
