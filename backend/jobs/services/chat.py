import logging
from collections.abc import Sequence
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

# Plain string constant for canned decline — deterministic, zero-cost, instant
CANNED_DECLINE: str = "I'm sorry, but I couldn't find any candidate information relevant to your question for this job posting."
CANNED_DECLINE_RESPONSE = CANNED_DECLINE

# Placeholder threshold for pre-filtering:
# Neon/pgvector returns negative inner product (<#>):
# - Relevant chunks have negative distance (e.g. -0.5 to -0.9), indicating positive dot-product similarity.
# - Out-of-scope / irrelevant chunks produce values >= 0 (values between 0 and 1).
# Any distance >= 0.0 (or top similarity < 0.0) is canned before making an expensive Groq LLM call.
DEFAULT_SIMILARITY_THRESHOLD: float = getattr(
    settings, "CHAT_SIMILARITY_THRESHOLD", -0.20
)
BORDERLINE_SIMILARITY_THRESHOLD: float = getattr(
    settings, "CHAT_BORDERLINE_THRESHOLD", -0.35
)

# Caution clause injected when retrieval confidence is borderline (-0.35 <= distance < -0.20)
CAUTION_CLAUSE: str = (
    "Retrieval confidence for this query was low. If the provided context is "
    "insufficient to answer accurately, decline and briefly explain why rather than guessing."
)


def extract_top_score(chunks_or_score: Any) -> float | None:
    """
    Extract the top chunk distance/score from a variety of inputs:
    - Sequence of ResumeChunk objects (with chunk.distance attribute)
    - SessionRetrievalResult or object with .chunks attribute
    - Ranked list of tuples [(resume_id, score), ...]
    - Direct numeric float/int distance or score
    """
    if chunks_or_score is None:
        return None
    if isinstance(chunks_or_score, (int, float)):
        return float(chunks_or_score)
    if hasattr(chunks_or_score, "chunks"):
        chunks_or_score = chunks_or_score.chunks
    if isinstance(chunks_or_score, Sequence) and len(chunks_or_score) > 0:
        first = chunks_or_score[0]
        if hasattr(first, "distance"):
            return float(first.distance)
        if (
            isinstance(first, (tuple, list))
            and len(first) >= 2
            and isinstance(first[1], (int, float))
        ):
            return float(first[1])
    return None


def should_decline_query(
    chunks_or_score: Any,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> bool:
    """
    Deterministic gate before any Groq LLM call.
    Returns True if query should be DECLINED (below relevance threshold or no hits).
    Returns False if query passes the pre-filter and should proceed to LLM.
    """
    score = extract_top_score(chunks_or_score)
    if score is None:
        logger.info("Chat pre-filter: No candidates/chunks retrieved. Declining query.")
        return True

    # Instrument and log scores to facilitate calibration with real data
    logger.info(
        "Chat pre-filter instrumentation: top_score=%s (similarity=%s), threshold=%s",
        score,
        -score,
        threshold,
    )

    # In pgvector's MaxInnerProduct, distance = -dot_product.
    # Negative distance means positive semantic alignment.
    # Values between 0 and 1 (distance >= 0) are irrelevant and must not proceed to LLM.
    if score >= threshold:
        logger.info(
            "Chat pre-filter: top score %s >= threshold %s. Canned decline triggered.",
            score,
            threshold,
        )
        return True

    return False


def get_canned_decline_if_irrelevant(
    chunks_or_score: Any,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    canned_response: str = CANNED_DECLINE,
) -> str | None:
    """
    Single deterministic check before any Groq call:
    if top_result_score is below threshold (distance >= threshold or empty),
    returns the canned decline string constant. Otherwise returns None.
    """
    if should_decline_query(chunks_or_score, threshold=threshold):
        return canned_response
    return None


def check_similarity_filter(
    chunks_or_score: Any,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    canned_response: str = CANNED_DECLINE,
) -> tuple[bool, str | None]:
    """
    Convenience tuple check:
    Returns (proceed_to_llm: bool, decline_message: str | None).
    """
    decline = get_canned_decline_if_irrelevant(
        chunks_or_score, threshold=threshold, canned_response=canned_response
    )
    if decline is not None:
        return False, decline
    return True, None


def is_borderline_query(
    chunks_or_score: Any,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    borderline_threshold: float = BORDERLINE_SIMILARITY_THRESHOLD,
) -> bool:
    """
    Returns True if top result distance falls into the borderline band:
    borderline_threshold <= distance < threshold (e.g. -0.35 <= distance < -0.20).
    """
    score = extract_top_score(chunks_or_score)
    if score is None:
        return False
    return borderline_threshold <= score < threshold


def get_confidence_band(
    chunks_or_score: Any,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    borderline_threshold: float = BORDERLINE_SIMILARITY_THRESHOLD,
) -> str:
    """
    Classifies retrieval relevance into one of three deterministic bands:
    - 'decline': distance >= -0.20 or no chunks (unrelated query, instant canned decline)
    - 'borderline': -0.35 <= distance < -0.20 (weak context, proceed to LLM with caution clause)
    - 'confident': distance < -0.35 (strong context, standard LLM prompt)
    """
    score = extract_top_score(chunks_or_score)
    if score is None or score >= threshold:
        return "decline"
    if score >= borderline_threshold:
        return "borderline"
    return "confident"


# ---------------------------------------------------------------------------
# Step 5 — Context & History Assembly + Groq LLM Call (openai/gpt-oss-120b)
# Context window: 131,072 tokens (~125k+ tokens headroom with N=10 messages)
# ---------------------------------------------------------------------------
GROQ_CHAT_MODEL: str = "openai/gpt-oss-120b"

DEFAULT_SYSTEM_PROMPT: str = (
    "You are an AI assistant helping recruiters evaluate and screen candidates for a job opening. "
    "Use only the provided candidate resume chunks to answer the user's questions about candidate qualifications, skills, and experience.\n\n"
    "GRACEFUL DECLINE INSTRUCTION:\n"
    "If the provided resume context does not contain enough information to answer the question, "
    "or if the question is out of scope for the available candidates, politely and gracefully decline to answer. "
    "State clearly that the requested information is not found in the candidates' resumes for this job opening. "
    "Do not invent, speculate, or extrapolate details not present in the chunks."
)


def format_chunks_context(chunks: Sequence[Any]) -> str:
    """
    Formats retrieved resume chunks into labeled context blocks.
    """
    if not chunks:
        return "No candidate resume chunks available."

    sections = []
    for idx, chunk in enumerate(chunks, 1):
        resume = getattr(chunk, "resume", None)
        filename = getattr(
            resume,
            "original_filename",
            f"Resume #{getattr(chunk, 'resume_id', idx)}",
        )
        chunk_text = getattr(chunk, "chunk_text", str(chunk)).strip()
        sections.append(f"--- Candidate Chunk {idx} ({filename}) ---\n{chunk_text}")
    return "\n\n".join(sections)


def build_chat_prompt_messages(
    session: Any,
    query: str,
    chunks: Sequence[Any] | None = None,
    history_limit: int = 10,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    caution_clause: str | None = None,
    auto_detect_caution: bool = True,
) -> list[dict[str, str]]:
    """
    Concatenates:
    (1) System prompt with graceful-decline instruction baked in as text (and caution clause if borderline).
    (2) The retrieved chunks from Step 3.
    (3) The last N=10 messages from ChatMessage for this session (reversed for chronological order).
    (4) The new user query.
    """
    if caution_clause is None and auto_detect_caution and chunks:
        if is_borderline_query(chunks):
            caution_clause = CAUTION_CLAUSE

    context_text = format_chunks_context(chunks or [])
    system_sections = [system_prompt]
    if caution_clause:
        system_sections.append(f"CAUTION:\n{caution_clause}")
    system_sections.append(f"=== CANDIDATE RESUME CONTEXT ===\n{context_text}")
    full_system_message = "\n\n".join(system_sections)

    messages = [{"role": "system", "content": full_system_message}]

    # Fetch last N=10 messages in reverse order (-created_at) then reverse to chronological
    if hasattr(session, "messages"):
        recent_messages = list(session.messages.order_by("-created_at")[:history_limit])
        recent_messages.reverse()
        for msg in recent_messages:
            messages.append({"role": msg.role, "content": msg.content})

    # Append new user query
    messages.append({"role": "user", "content": query})
    return messages


async def stream_chat_tokens(
    session: Any,
    query: str,
    chunks: Sequence[Any] | None = None,
    history_limit: int = 10,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    caution_clause: str | None = None,
    model: str = GROQ_CHAT_MODEL,
    temperature: float = 0.2,
):
    """
    Assembles context and history, then yields token delta strings from AsyncGroq (openai/gpt-oss-120b).
    """
    from jobs.groq_client import async_groq_client_instance

    messages = build_chat_prompt_messages(
        session=session,
        query=query,
        chunks=chunks,
        history_limit=history_limit,
        system_prompt=system_prompt,
        caution_clause=caution_clause,
    )

    client = async_groq_client_instance
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        temperature=temperature,
    )
    async for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta


async def generate_chat_response(
    session: Any,
    query: str,
    chunks: Sequence[Any] | None = None,
    history_limit: int = 10,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    caution_clause: str | None = None,
    model: str = GROQ_CHAT_MODEL,
    temperature: float = 0.2,
) -> str:
    """
    Assembles context and history, then queries AsyncGroq (openai/gpt-oss-120b) asynchronously.
    """
    from jobs.groq_client import async_groq_client_instance

    messages = build_chat_prompt_messages(
        session=session,
        query=query,
        chunks=chunks,
        history_limit=history_limit,
        system_prompt=system_prompt,
        caution_clause=caution_clause,
    )

    client = async_groq_client_instance
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""
