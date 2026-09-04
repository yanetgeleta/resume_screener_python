import os

import dj_database_url

from .base import *

DEBUG = False
TESTING = True

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ["DATABASE_URL"],  # set by CI step after branch creation
        conn_max_age=0,
        ssl_require=True,
    )
}

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}


GROQ_API_KEY = "dummy-test-key-never-call-network"
