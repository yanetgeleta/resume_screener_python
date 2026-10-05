from django.core import signing

# Salt creates a distinct cryptographic namespace so this token
# cannot be used for password resets or other signed operations.
EMAIL_VERIFICATION_SALT = "email-verification-token"
DEFAULT_TOKEN_MAX_AGE = 60 * 60 * 24  # 24 hours in seconds


def generate_verification_token(instance) -> str:
    """
    Encodes the model's app_label, model_name, and primary key into
    a tamper-proof, timestamped cryptographic token.
    """
    payload = {
        "model": instance._meta.label_lower,  # e.g., "accounts.company" or "applicants.applicant"
        "pk": str(instance.pk),  # stringified to safely handle UUIDs or ints
    }
    return signing.dumps(payload, salt=EMAIL_VERIFICATION_SALT)


def verify_verification_token(
    token: str, max_age_seconds: int = DEFAULT_TOKEN_MAX_AGE
) -> dict | None:
    """
    Verifies the token's cryptographic signature and validates expiry.
    Returns the decoded payload dict {"model": str, "pk": str} on success,
    or None if the token is tampered with, malformed, or expired.
    """
    try:
        data = signing.loads(
            token,
            salt=EMAIL_VERIFICATION_SALT,
            max_age=max_age_seconds,
        )
        return data
    except (signing.BadSignature, signing.SignatureExpired):
        return None
