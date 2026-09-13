import os

from dotenv import load_dotenv
from groq import AsyncGroq, Groq

load_dotenv()

groq_client_instance = Groq(api_key=os.getenv("GROQ_API_KEY", "mock-key-for-tests"))

async_groq_client_instance = AsyncGroq(
    api_key=os.getenv("GROQ_API_KEY", "mock-key-for-tests")
)
