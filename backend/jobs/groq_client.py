from django.conf import settings
from groq import AsyncGroq, Groq

groq_client_instance = Groq(
    api_key=getattr(settings, "GROQ_API_KEY", "mock-key-for-tests")
)

async_groq_client_instance = AsyncGroq(
    api_key=getattr(settings, "GROQ_API_KEY", "mock-key-for-tests")
)

