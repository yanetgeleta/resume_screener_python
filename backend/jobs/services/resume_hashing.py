import hashlib


def hash_resume_text(text: str | None):
    if not text or not text.strip():
        return None
    normalized_text = " ".join(text.lower().split())
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
