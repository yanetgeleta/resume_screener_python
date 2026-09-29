import logging

from accounts.models import Company
from rest_framework import permissions
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken, Token

from applicants.models import Applicant

logger = logging.getLogger(__name__)


def generate_applicant_tokens(applicant: Applicant) -> dict:
    """
    Issues parallel JWT tokens for Applicant entities, keeping them distinct
    from standard Company AUTH_USER_MODEL sessions.
    """
    refresh = RefreshToken()
    refresh["user_type"] = "applicant"
    refresh["user_id"] = applicant.id
    refresh["email"] = applicant.email

    access = refresh.access_token
    access["user_type"] = "applicant"
    access["user_id"] = applicant.id
    access["email"] = applicant.email

    return {
        "refresh": str(refresh),
        "access": str(access),
    }


class MultiUserJWTAuthentication(JWTAuthentication):
    """
    Unified JWT Authentication class that authenticates both:
    1. Company users (AUTH_USER_MODEL) when user_type is not 'applicant'.
    2. Applicant users (applicants.Applicant) when user_type == 'applicant'.
    """

    def get_user(self, validated_token: Token):
        user_type = validated_token.get("user_type")

        if user_type == "applicant":
            user_id = validated_token.get("user_id")
            if not user_id:
                raise AuthenticationFailed(
                    "Token contained no recognizable applicant identification",
                    code="bad_authorization_header",
                )
            try:
                applicant = Applicant.objects.get(id=user_id)
            except Applicant.DoesNotExist:
                raise AuthenticationFailed(
                    "Applicant not found",
                    code="user_not_found",
                )

            if not applicant.is_active:
                raise AuthenticationFailed(
                    "Applicant account is inactive",
                    code="user_inactive",
                )

            return applicant

        # Fallback to standard AUTH_USER_MODEL (Company)
        return super().get_user(validated_token)


class IsApplicant(permissions.BasePermission):
    """
    Allows access only to authenticated Applicant users.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, Applicant)
        )


class IsCompany(permissions.BasePermission):
    """
    Allows access only to authenticated Company (recruiter) users.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, Company)  # Explicit inclusion
        )
