from unittest.mock import MagicMock

import pytest
from jobs.models import ChatMessage
from jobs.services.chat import (
    CAUTION_CLAUSE,
    DEFAULT_SYSTEM_PROMPT,
    GROQ_CHAT_MODEL,
    build_chat_prompt_messages,
    format_chunks_context,
    generate_chat_response,
)

from tests.factories import (
    ChatMessageFactory,
    ChatSessionFactory,
    CompanyFactory,
    JobFactory,
    ResumeChunkFactory,
    ResumeFactory,
)


import os

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

pytestmark = pytest.mark.django_db



def test_format_chunks_context():
    c1 = MagicMock(chunk_text="Experience with Python, Django, PostgreSQL.")
    c1.resume = MagicMock(original_filename="alice_resume.pdf")
    c1.resume_id = 101

    context = format_chunks_context([c1])
    assert "alice_resume.pdf" in context
    assert "Experience with Python, Django, PostgreSQL." in context


def test_build_chat_prompt_messages_concatenation():
    company = CompanyFactory()
    job = JobFactory(company=company)
    session = ChatSessionFactory(company=company, job=job)
    resume = ResumeFactory(company=company, original_filename="bob_cv.pdf")

    c1 = ResumeChunkFactory(
        resume=resume, chunk_text="Bob has 5 years of React and TypeScript experience."
    )

    # Add 3 chat messages in history
    msg1 = ChatMessageFactory(
        session=session, role=ChatMessage.Role.USER, content="Hello"
    )
    msg2 = ChatMessageFactory(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content="Hi! How can I help with candidate screening?",
    )
    msg3 = ChatMessageFactory(
        session=session,
        role=ChatMessage.Role.USER,
        content="Does anyone know React?",
    )

    query = "What about TypeScript?"
    messages = build_chat_prompt_messages(session, query=query, chunks=[c1])

    # 1. System prompt with graceful decline instruction baked in + retrieved chunks
    assert messages[0]["role"] == "system"
    assert "GRACEFUL DECLINE INSTRUCTION" in messages[0]["content"]
    assert "Bob has 5 years of React and TypeScript experience." in messages[0]["content"]
    assert "bob_cv.pdf" in messages[0]["content"]

    # 2. History in chronological order
    assert len(messages) == 1 + 3 + 1  # system + 3 history + new query
    assert messages[1] == {"role": "user", "content": "Hello"}
    assert messages[2] == {
        "role": "assistant",
        "content": "Hi! How can I help with candidate screening?",
    }
    assert messages[3] == {"role": "user", "content": "Does anyone know React?"}

    # 3. New user query as the last message
    assert messages[-1] == {"role": "user", "content": query}


def test_history_window_n10_truncation_and_chronology():
    """
    Ensure only the last N=10 messages are pulled via .order_by("-created_at")[:10]
    and reversed so they are chronologically ordered.
    """
    company = CompanyFactory()
    job = JobFactory(company=company)
    session = ChatSessionFactory(company=company, job=job)

    # Create 15 messages (idx 0 to 14)
    created_messages = []
    for i in range(15):
        role = ChatMessage.Role.USER if i % 2 == 0 else ChatMessage.Role.ASSISTANT
        msg = ChatMessageFactory(session=session, role=role, content=f"Message #{i}")
        created_messages.append(msg)

    messages = build_chat_prompt_messages(session, query="Latest query", history_limit=10)

    # Expected: System prompt (1) + 10 history messages + user query (1) = 12 total
    assert len(messages) == 12

    # Verify the 10 messages correspond to indices 5..14 in chronological order
    history_in_prompt = messages[1:-1]
    for idx, expected_num in enumerate(range(5, 15)):
        assert history_in_prompt[idx]["content"] == f"Message #{expected_num}"

    assert messages[-1]["content"] == "Latest query"


import asyncio
from functools import wraps


def run_async(coro_fn):
    @wraps(coro_fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(coro_fn(*args, **kwargs))

    return wrapper


@run_async
async def test_generate_chat_response_calls_groq(mocker):

    from unittest.mock import AsyncMock

    company = CompanyFactory()
    job = JobFactory(company=company)
    session = ChatSessionFactory(company=company, job=job)

    # Mock AsyncGroq client
    mock_client = mocker.patch("jobs.groq_client.async_groq_client_instance")
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Bob is proficient in TypeScript."))
    ]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    reply = await generate_chat_response(session, query="Does Bob know TypeScript?")

    assert reply == "Bob is proficient in TypeScript."
    mock_client.chat.completions.create.assert_awaited_once()
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "openai/gpt-oss-120b"
    assert call_kwargs["model"] == GROQ_CHAT_MODEL
    assert len(call_kwargs["messages"]) >= 2
    assert call_kwargs["messages"][0]["role"] == "system"
    assert call_kwargs["messages"][-1] == {
        "role": "user",
        "content": "Does Bob know TypeScript?",
    }


def test_borderline_prompt_injects_caution_clause():
    """
    Step 7: For borderline distances (-0.35 <= distance < -0.20),
    the caution clause must be injected into the system prompt,
    while retrieved chunks are still passed as-is.
    """
    company = CompanyFactory()
    job = JobFactory(company=company)
    session = ChatSessionFactory(company=company, job=job)

    chunk = MagicMock(chunk_text="Some weak mention of Python.")
    chunk.resume = MagicMock(original_filename="cand.pdf")
    chunk.resume_id = 1
    chunk.distance = -0.25  # Borderline: -0.35 <= -0.25 < -0.20

    messages = build_chat_prompt_messages(session, query="Python dev?", chunks=[chunk])

    sys_content = messages[0]["content"]
    assert "CAUTION:" in sys_content
    assert CAUTION_CLAUSE in sys_content
    assert "Retrieval confidence for this query was low." in sys_content
    # Weak chunks still present
    assert "Some weak mention of Python." in sys_content


def test_confident_prompt_omits_caution_clause():
    """
    Step 7: For confident distances (distance < -0.35),
    no caution clause is injected into the prompt.
    """
    company = CompanyFactory()
    job = JobFactory(company=company)
    session = ChatSessionFactory(company=company, job=job)

    chunk = MagicMock(chunk_text="Strong Python Django experience.")
    chunk.resume = MagicMock(original_filename="alice.pdf")
    chunk.resume_id = 2
    chunk.distance = -0.55  # Confident: < -0.35

    messages = build_chat_prompt_messages(session, query="Python dev?", chunks=[chunk])

    sys_content = messages[0]["content"]
    assert "CAUTION:" not in sys_content
    assert "Retrieval confidence for this query was low." not in sys_content
    assert "Strong Python Django experience." in sys_content

