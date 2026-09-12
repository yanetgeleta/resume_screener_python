from collections import defaultdict
from typing import NamedTuple

from pgvector.django import MaxInnerProduct

from jobs.models import ResumeChunk
from jobs.services.embedding import embed_text


class SessionRetrievalResult(NamedTuple):
    chunks: list[ResumeChunk]
    ranked: list[tuple[int, float]]


def _extract_session_job_id(session) -> int:
    if hasattr(session, "job_id") and session.job_id is not None:
        return session.job_id
    if hasattr(session, "job"):
        job = session.job
        return getattr(job, "id", job)
    if hasattr(session, "id"):
        return session.id
    return int(session)


def fetch_candidate_chunks(
    job,
    multiplier: int = 4,
    query: str | None = None,
    limit: int | None = None,
):
    """
    Over-fetch resume chunks for a job, tenant-scoped through
    Resume -> Application -> Job. Ordered by MaxInnerProduct distance
    (smaller = more similar, per pgvector's negation convention).
    If query is provided, delegates to fetch_candidate_chunks_for_session.
    """
    if query is not None:
        return fetch_candidate_chunks_for_session(
            session=job, query=query, multiplier=multiplier, limit=limit
        )

    if limit is not None:
        over_fetch_n = limit
    else:
        over_fetch_n = job.head_count * multiplier

    return list(
        ResumeChunk.objects.filter(resume__applications__job=job)
        .annotate(distance=MaxInnerProduct("embedding", job.embedding))
        .order_by("distance")[:over_fetch_n]
        .select_related("resume")
    )


def fetch_candidate_chunks_for_session(
    session,
    query: str,
    multiplier: int = 4,
    limit: int | None = None,
) -> list[ResumeChunk]:
    """
    Over-fetch resume chunks for a chat session matching user query,
    tenant-scoped strictly through session.job_id (Resume -> Application -> Job).
    Ordered by MaxInnerProduct distance (smaller = more similar).
    """
    query_embedding = embed_text(query)
    job_id = _extract_session_job_id(session)

    qs = ResumeChunk.objects.filter(resume__applications__job_id=job_id)
    if hasattr(session, "company_id") and session.company_id is not None:
        qs = qs.filter(resume__applications__job__company_id=session.company_id)

    if limit is not None:
        over_fetch_n = limit
    else:
        head_count = getattr(getattr(session, "job", None), "head_count", None)
        over_fetch_n = (head_count * multiplier) if head_count else (5 * multiplier)

    return list(
        qs.annotate(distance=MaxInnerProduct("embedding", query_embedding))
        .order_by("distance")[:over_fetch_n]
        .select_related("resume")
    )


def aggregate_top2_mean(chunks) -> list[tuple[int, float]]:
    """
    Collapse chunk-level hits to one score per resume_id, using the
    mean of each resume's best 2 chunk distances. Returns
    [(resume_id, score), ...] sorted ascending (best match first).
    """
    by_resume: dict[int, list[float]] = defaultdict(list)
    for chunk in chunks:
        by_resume[chunk.resume_id].append(chunk.distance)

    scored = []
    for resume_id, distances in by_resume.items():
        distances.sort()
        top2 = distances[:2]
        scored.append((resume_id, sum(top2) / len(top2)))

    scored.sort(key=lambda pair: pair[1])
    return scored


def retrieve_for_session(
    session,
    query: str,
    multiplier: int = 4,
    limit: int | None = None,
) -> SessionRetrievalResult:
    """
    Run retrieval for a chat session:
    1. Embeds user query with jobs.services.embedding.
    2. Runs pgvector similarity search filtered to chunks WHERE job_id = session.job_id.
    3. Reuses Phase 4 aggregate_top2_mean to score candidates by resume_id.

    Returns SessionRetrievalResult(chunks, ranked), unpackable as (chunks, ranked).
    """
    chunks = fetch_candidate_chunks_for_session(
        session=session,
        query=query,
        multiplier=multiplier,
        limit=limit,
    )
    ranked = aggregate_top2_mean(chunks)
    return SessionRetrievalResult(chunks=chunks, ranked=ranked)


# Aliases for convenience
fetch_session_candidate_chunks = fetch_candidate_chunks_for_session
retrieve_candidate_chunks_for_session = fetch_candidate_chunks_for_session
retrieve_chunks_for_session = fetch_candidate_chunks_for_session

# Chat & pre-filter imports & re-exports
from jobs.services.chat import (  # noqa: E402
    CANNED_DECLINE,
    CANNED_DECLINE_RESPONSE,
    DEFAULT_SIMILARITY_THRESHOLD,
    GROQ_CHAT_MODEL,
    build_chat_prompt_messages,
    check_similarity_filter,
    generate_chat_response,
    get_canned_decline_if_irrelevant,
    should_decline_query,
)



