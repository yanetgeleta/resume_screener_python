import asyncio
import json
import os
from functools import wraps
from unittest.mock import AsyncMock, MagicMock

import pytest
from django.test import AsyncRequestFactory

from jobs.models import ChatMessage
from jobs.views import chat_stream_view
from tests.factories import (
    ApplicationFactory,
    ChatSessionFactory,
    CompanyFactory,
    JobFactory,
    ResumeChunkFactory,
    ResumeFactory,
)

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"


def run_async(coro_fn):
    @wraps(coro_fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(coro_fn(*args, **kwargs))

    return wrapper


class MockAsyncStream:
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


@run_async
async def test_chat_stream_multi_candidate_ranking_summary(mocker, db):
    """
    Verifies that a system-synthesized query requesting top candidates ranked by final_score:
    - Bypasses vector decline prefilter when scored applications exist.
    - Successfully calls Groq with structured candidate context.
    - Streams tokens via SSE and persists messages.
    - Honors the POST /jobs/{jobId}/chat/{sessionId}/ endpoint.
    """
    company = CompanyFactory()
    job = JobFactory(company=company, head_count=2)
    session = ChatSessionFactory(company=company, job=job)

    resume1 = ResumeFactory(
        company=company,
        original_filename="Alice_Resume.pdf",
        skills=["Python", "Django"],
        experience_years=5,
    )
    resume2 = ResumeFactory(
        company=company,
        original_filename="Bob_Resume.pdf",
        skills=["React", "TypeScript"],
        experience_years=3,
    )

    ApplicationFactory(
        job=job,
        resume=resume1,
        final_score=0.92,
        retrieval_score=-0.85,
        llm_profile={
            "summary": "Outstanding backend engineer.",
            "strengths": ["Deep Python expertise", "Scalable systems"],
            "gaps": ["No frontend"],
        },
    )
    ApplicationFactory(
        job=job,
        resume=resume2,
        final_score=0.81,
        retrieval_score=-0.70,
        llm_profile={
            "summary": "Solid frontend developer.",
            "strengths": ["React expert"],
            "gaps": ["Junior backend"],
        },
    )

    # Mock Groq streaming response
    mock_groq = mocker.patch("jobs.views.async_groq_client_instance")
    stream_tokens = [
        "Top candidates:\n",
        "1. Alice - Score: 0.92\n",
        "Strengths: Deep Python expertise\n",
        "2. Bob - Score: 0.81\n",
    ]
    mock_groq.chat.completions.create = AsyncMock(
        return_value=MockAsyncStream(stream_tokens)
    )

    rf = AsyncRequestFactory()
    synthesized_query = (
        "Please provide a profile of the top 2 candidates ranked by final_score, "
        "each with strengths, summary, and gaps."
    )
    request = rf.post(
        f"/jobs/{job.id}/chat/{session.id}/",
        data=json.dumps({"query": synthesized_query}),
        content_type="application/json",
    )
    request.user = company

    response = await chat_stream_view(request, session_id=session.id, job_id=job.id)

    assert response.status_code == 200
    assert response["Content-Type"] == "text/event-stream"

    chunks_received = []
    async for item in response.streaming_content:
        chunks_received.append(item.decode("utf-8") if isinstance(item, bytes) else item)

    full_stream_text = "".join(chunks_received)
    assert 'data: {"content": "Top candidates:\\n"}' in full_stream_text
    assert 'data: {"content": "1. Alice - Score: 0.92\\n"}' in full_stream_text
    assert "data: [DONE]" in full_stream_text

    # Verify messages in DB
    messages = [m async for m in session.messages.order_by("created_at")]
    assert len(messages) == 2
    assert messages[0].role == ChatMessage.Role.USER
    assert messages[0].content == synthesized_query
    assert messages[1].role == ChatMessage.Role.ASSISTANT
    assert "Top candidates:" in messages[1].content
