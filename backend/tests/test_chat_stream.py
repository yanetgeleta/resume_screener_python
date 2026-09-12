import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncRequestFactory
from jobs.models import ChatMessage
from jobs.services.chat import CANNED_DECLINE, CAUTION_CLAUSE
from jobs.views import chat_stream_view


from tests.factories import (
    ApplicationFactory,
    ChatSessionFactory,
    CompanyFactory,
    JobFactory,
    ResumeChunkFactory,
    ResumeFactory,
)

import asyncio
import os
from functools import wraps

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

pytestmark = pytest.mark.django_db



def run_async(coro_fn):
    @wraps(coro_fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(coro_fn(*args, **kwargs))

    return wrapper


class MockAsyncStream:
    """Simulates an AsyncGroq token stream yielding ChatCompletionChunk-like objects."""

    def __init__(self, deltas: list[str]):
        self.deltas = deltas

    def __aiter__(self):
        self._iter = iter(self.deltas)
        return self

    async def __anext__(self):
        try:
            delta = next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

        chunk = MagicMock()
        choice = MagicMock()
        choice.delta.content = delta
        chunk.choices = [choice]
        return chunk


@pytest.fixture
def dummy_vector():
    return [1.0 / (384**0.5)] * 384


@run_async
async def test_chat_stream_view_happy_path(mocker, dummy_vector):
    """
    Happy path test:
    - Token chunks stream via SSE data: events.
    - Full text is accumulated.
    - Both user query and complete assistant reply are persisted to ChatMessage.
    """
    company = CompanyFactory()
    job = JobFactory(company=company)
    session = ChatSessionFactory(company=company, job=job)

    resume = ResumeFactory(company=company)
    ApplicationFactory(job=job, resume=resume)
    ResumeChunkFactory(
        resume=resume, chunk_text="Alice knows Python and Django.", embedding=dummy_vector
    )

    mocker.patch("jobs.services.retrieval.embed_text", return_value=dummy_vector)

    # Mock AsyncGroq stream
    mock_groq = mocker.patch("jobs.views.async_groq_client_instance")
    mock_stream = MockAsyncStream(["Alice ", "has ", "strong ", "Python."])
    mock_groq.chat.completions.create = AsyncMock(return_value=mock_stream)

    rf = AsyncRequestFactory()
    request = rf.post(
        f"/jobs/sessions/{session.id}/stream/",
        data=json.dumps({"query": "Tell me about Alice's Python experience."}),
        content_type="application/json",
    )
    request.user = company

    response = await chat_stream_view(request, session_id=session.id)

    assert response.status_code == 200
    assert response["Content-Type"] == "text/event-stream"

    # Consume the SSE stream
    chunks_received = []
    async for item in response.streaming_content:
        chunks_received.append(item.decode("utf-8") if isinstance(item, bytes) else item)

    full_stream_text = "".join(chunks_received)
    assert 'data: {"content": "Alice "}' in full_stream_text
    assert 'data: {"content": "has "}' in full_stream_text
    assert 'data: {"content": "strong "}' in full_stream_text
    assert 'data: {"content": "Python."}' in full_stream_text
    assert "data: [DONE]" in full_stream_text

    # Verify persistence: 1 user message, 1 assistant message
    messages = [m async for m in session.messages.order_by("created_at")]
    assert len(messages) == 2

    user_msg = messages[0]
    assert user_msg.role == ChatMessage.Role.USER
    assert user_msg.content == "Tell me about Alice's Python experience."

    assistant_msg = messages[1]
    assert assistant_msg.role == ChatMessage.Role.ASSISTANT
    assert assistant_msg.content == "Alice has strong Python."


@run_async
async def test_chat_stream_client_disconnect_saves_partial_content(mocker, dummy_vector):
    """
    Client disconnect test:
    - Client disconnects mid-stream (stops reading and closes generator).
    - Completion-guard / finally block catches the exit.
    - Persists partial accumulated text so far into ChatMessage.
    """
    company = CompanyFactory()
    job = JobFactory(company=company)
    session = ChatSessionFactory(company=company, job=job)

    resume = ResumeFactory(company=company)
    ApplicationFactory(job=job, resume=resume)
    ResumeChunkFactory(
        resume=resume, chunk_text="Candidate knows Docker and Kubernetes.", embedding=dummy_vector
    )

    mocker.patch("jobs.services.retrieval.embed_text", return_value=dummy_vector)

    mock_groq = mocker.patch("jobs.views.async_groq_client_instance")
    mock_stream = MockAsyncStream(["Token1 ", "Token2 ", "Token3 ", "Token4 "])
    mock_groq.chat.completions.create = AsyncMock(return_value=mock_stream)

    rf = AsyncRequestFactory()
    request = rf.post(
        f"/jobs/sessions/{session.id}/stream/",
        data=json.dumps({"query": "Tell me about Docker experience."}),
        content_type="application/json",
    )
    request.user = company

    response = await chat_stream_view(request, session_id=session.id)
    assert response.status_code == 200

    # Simulate client disconnect after 2 chunks:
    stream_iter = response.streaming_content
    c1 = await anext(stream_iter)
    c2 = await anext(stream_iter)
    assert "Token1" in (c1.decode("utf-8") if isinstance(c1, bytes) else c1)
    assert "Token2" in (c2.decode("utf-8") if isinstance(c2, bytes) else c2)

    # Client drops connection!
    if hasattr(response, "_iterator") and hasattr(response._iterator, "aclose"):
        await response._iterator.aclose()
    else:
        await stream_iter.aclose()


    # Verify persistence: partial content "Token1 Token2 " should be saved!
    messages = [m async for m in session.messages.order_by("created_at")]
    assert len(messages) == 2

    assert messages[0].role == ChatMessage.Role.USER
    assert messages[0].content == "Tell me about Docker experience."

    assert messages[1].role == ChatMessage.Role.ASSISTANT
    assert messages[1].content == "Token1 Token2 "


@run_async
async def test_chat_stream_view_canned_decline_on_out_of_scope(mocker, dummy_vector):
    """
    Step 4 pre-filter integration in stream:
    - Out of scope query (similarity < 0, distance >= 0) is declined.
    - Yields canned decline SSE event and persists assistant message with canned text.
    - Groq is NEVER called.
    """
    company = CompanyFactory()
    job = JobFactory(company=company)
    session = ChatSessionFactory(company=company, job=job)

    resume = ResumeFactory(company=company)
    ApplicationFactory(job=job, resume=resume)
    # Chunk with dummy_vector
    ResumeChunkFactory(
        resume=resume, chunk_text="Python developer.", embedding=dummy_vector
    )

    # Query with opposite vector -> distance >= 0.0 (unrelated)
    opposite_vector = [-x for x in dummy_vector]
    mocker.patch("jobs.services.retrieval.embed_text", return_value=opposite_vector)

    mock_groq = mocker.patch("jobs.views.async_groq_client_instance")
    mock_groq.chat.completions.create = AsyncMock()

    rf = AsyncRequestFactory()
    request = rf.post(
        f"/jobs/sessions/{session.id}/stream/",
        data=json.dumps({"query": "Can candidates pilot an airplane?"}),
        content_type="application/json",
    )
    request.user = company

    response = await chat_stream_view(request, session_id=session.id)
    assert response.status_code == 200

    chunks_received = []
    async for item in response.streaming_content:
        chunks_received.append(item.decode("utf-8") if isinstance(item, bytes) else item)

    full_text = "".join(chunks_received)
    assert CANNED_DECLINE in full_text
    assert "data: [DONE]" in full_text

    # Groq was NOT called!
    mock_groq.chat.completions.create.assert_not_called()

    # Canned decline was persisted to ChatMessage
    messages = [m async for m in session.messages.order_by("created_at")]
    assert len(messages) == 2
    assert messages[0].content == "Can candidates pilot an airplane?"
    assert messages[1].content == CANNED_DECLINE


@run_async
async def test_chat_stream_view_permission_denied_for_other_tenant():
    """
    Cross-tenant check: Company B cannot stream Company A's session.
    """
    company_a = CompanyFactory()
    company_b = CompanyFactory()

    job_a = JobFactory(company=company_a)
    session_a = ChatSessionFactory(company=company_a, job=job_a)

    rf = AsyncRequestFactory()
    request = rf.post(
        f"/jobs/sessions/{session_a.id}/stream/",
        data=json.dumps({"query": "Steal data"}),
        content_type="application/json",
    )
    request.user = company_b

    response = await chat_stream_view(request, session_id=session_a.id)
    assert response.status_code == 403


@run_async
async def test_chat_stream_view_borderline_injects_caution_clause(mocker):
    """
    Step 7 borderline handling in chat_stream_view:
    - Distance in borderline band (-0.35 <= distance < -0.20) proceeds to Groq.
    - Caution clause is injected into the prompt sent to Groq.
    - Weak chunks are included as-is.
    - Whatever Groq returns is streamed and persisted to ChatMessage normally.
    """
    company = CompanyFactory()
    job = JobFactory(company=company)
    session = ChatSessionFactory(company=company, job=job)

    # Mock chunk with borderline distance
    chunk = MagicMock(chunk_text="A vague mention of cloud infrastructure.")
    chunk.resume = MagicMock(original_filename="cloud_resume.pdf")
    chunk.resume_id = 42
    chunk.distance = -0.28  # Borderline: -0.35 <= -0.28 < -0.20

    mocker.patch(
        "jobs.views.fetch_candidate_chunks_for_session",
        return_value=[chunk],
    )

    mock_groq = mocker.patch("jobs.views.async_groq_client_instance")
    mock_stream = MockAsyncStream(["I ", "cannot ", "confirm ", "AWS ", "skills."])
    mock_groq.chat.completions.create = AsyncMock(return_value=mock_stream)

    rf = AsyncRequestFactory()
    request = rf.post(
        f"/jobs/sessions/{session.id}/stream/",
        data=json.dumps({"query": "Does candidate know AWS?"}),
        content_type="application/json",
    )
    request.user = company

    response = await chat_stream_view(request, session_id=session.id)
    assert response.status_code == 200

    chunks_received = []
    async for item in response.streaming_content:
        chunks_received.append(item.decode("utf-8") if isinstance(item, bytes) else item)

    full_text = "".join(chunks_received)
    assert "I cannot confirm AWS skills." in "".join(
        json.loads(line.replace("data: ", ""))["content"]
        for line in full_text.splitlines()
        if line.startswith("data: ") and not line.endswith("[DONE]")
    )

    # Groq was called with caution clause in messages
    mock_groq.chat.completions.create.assert_awaited_once()
    call_kwargs = mock_groq.chat.completions.create.call_args.kwargs
    system_msg = call_kwargs["messages"][0]["content"]
    assert "CAUTION:" in system_msg
    assert CAUTION_CLAUSE in system_msg
    assert "A vague mention of cloud infrastructure." in system_msg

    # Dialog turn persisted to ChatMessage
    messages = [m async for m in session.messages.order_by("created_at")]
    assert len(messages) == 2
    assert messages[0].content == "Does candidate know AWS?"
    assert messages[1].content == "I cannot confirm AWS skills."
