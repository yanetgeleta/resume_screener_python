from unittest.mock import MagicMock

import pytest
from jobs.services.chat import (
    BORDERLINE_SIMILARITY_THRESHOLD,
    CANNED_DECLINE,
    CANNED_DECLINE_RESPONSE,
    CAUTION_CLAUSE,
    DEFAULT_SIMILARITY_THRESHOLD,
    check_similarity_filter,
    get_canned_decline_if_irrelevant,
    get_confidence_band,
    is_borderline_query,
    should_decline_query,
)
from jobs.services.retrieval import (
    fetch_candidate_chunks_for_session,
)

from tests.factories import (
    ApplicationFactory,
    ChatSessionFactory,
    CompanyFactory,
    JobFactory,
    ResumeChunkFactory,
    ResumeFactory,
)


def test_canned_decline_constant():
    assert isinstance(CANNED_DECLINE, str)
    assert len(CANNED_DECLINE) > 0
    assert CANNED_DECLINE == CANNED_DECLINE_RESPONSE


def test_empty_chunks_declined():
    assert should_decline_query([]) is True
    assert should_decline_query(None) is True
    assert get_canned_decline_if_irrelevant([]) == CANNED_DECLINE
    proceed, message = check_similarity_filter([])
    assert proceed is False
    assert message == CANNED_DECLINE


def test_out_of_scope_query_declined():
    """
    In pgvector MaxInnerProduct (<#>), values between 0 and 1 (distance >= 0.0)
    represent non-positive semantic similarity (orthogonal or negative correlation).
    These should not proceed to LLM call.
    """
    chunk_irrelevant = MagicMock()
    chunk_irrelevant.distance = 0.25

    chunks = [chunk_irrelevant]
    assert should_decline_query(chunks, threshold=0.0) is True
    assert get_canned_decline_if_irrelevant(chunks, threshold=0.0) == CANNED_DECLINE

    proceed, message = check_similarity_filter(chunks, threshold=0.0)
    assert proceed is False
    assert message == CANNED_DECLINE


def test_relevant_query_passes_filter():
    """
    Negative distances (e.g. -0.65) indicate positive dot-product similarity.
    These must pass the pre-filter and proceed to LLM call.
    """
    chunk_relevant = MagicMock()
    chunk_relevant.distance = -0.65

    chunks = [chunk_relevant]
    assert should_decline_query(chunks, threshold=0.0) is False
    assert get_canned_decline_if_irrelevant(chunks, threshold=0.0) is None

    proceed, message = check_similarity_filter(chunks, threshold=0.0)
    assert proceed is True
    assert message is None


def test_custom_threshold_adjustment():
    """
    Verifies that the threshold can be tightened (e.g. from 0.0 to -0.4)
    based on real empirical data calibration.
    """
    chunk_weak = MagicMock()
    chunk_weak.distance = -0.2

    chunk_strong = MagicMock()
    chunk_strong.distance = -0.7

    # At threshold 0.0, -0.2 passes
    assert should_decline_query([chunk_weak], threshold=0.0) is False

    # When calibrated / tightened to -0.4:
    # -0.2 is >= -0.4 (weaker similarity), so it gets declined
    assert should_decline_query([chunk_weak], threshold=-0.4) is True
    # -0.7 is < -0.4 (stronger similarity), so it passes
    assert should_decline_query([chunk_strong], threshold=-0.4) is False


@pytest.fixture
def dummy_vector():
    return [1.0 / (384**0.5)] * 384


@pytest.mark.django_db
def test_retrieval_and_prefilter_integration(mocker, dummy_vector):
    """
    Integration test:
    - Relevant query produces negative distance -> passes pre-filter.
    - Out-of-scope query produces non-negative distance -> declined with canned response.
    """
    company = CompanyFactory()
    job = JobFactory(company=company, head_count=2)
    session = ChatSessionFactory(company=company, job=job)

    resume = ResumeFactory(company=company)
    ApplicationFactory(job=job, resume=resume)

    # Relevant chunk matching dummy_vector exactly (inner product = 1.0 -> distance = -1.0)
    c_relevant = ResumeChunkFactory(
        resume=resume, chunk_text="Senior Python Django engineer", embedding=dummy_vector
    )

    # 1. Relevant query -> dot product ~ 1.0 -> distance ~ -1.0
    mocker.patch("jobs.services.retrieval.embed_text", return_value=dummy_vector)
    chunks = fetch_candidate_chunks_for_session(session, query="Python engineer")
    assert len(chunks) > 0
    assert chunks[0].distance < 0.0
    assert get_canned_decline_if_irrelevant(chunks) is None

    # 2. Opposite/irrelevant query -> dot product = -1.0 -> distance = 1.0 (between 0 and 1)
    opposite_vector = [-x for x in dummy_vector]
    mocker.patch("jobs.services.retrieval.embed_text", return_value=opposite_vector)
    chunks_irrelevant = fetch_candidate_chunks_for_session(
        session, query="Astronaut scuba diver"
    )
    assert len(chunks_irrelevant) > 0
    assert chunks_irrelevant[0].distance >= 0.0
    assert (
        get_canned_decline_if_irrelevant(chunks_irrelevant)
        == CANNED_DECLINE
    )


def test_confidence_bands_routing():
    """
    Step 7 routing rules:
    - distance >= -0.20 -> 'decline'
    - -0.35 <= distance < -0.20 -> 'borderline'
    - distance < -0.35 -> 'confident'
    """
    # Empty / None
    assert get_confidence_band([]) == "decline"
    assert get_confidence_band(None) == "decline"
    assert is_borderline_query([]) is False

    # Out of scope / weak: >= -0.20
    chunk_irrelevant = MagicMock(distance=0.1)
    chunk_cutoff = MagicMock(distance=-0.20)
    chunk_weak = MagicMock(distance=-0.15)
    assert get_confidence_band([chunk_irrelevant]) == "decline"
    assert get_confidence_band([chunk_cutoff]) == "decline"
    assert get_confidence_band([chunk_weak]) == "decline"
    assert is_borderline_query([chunk_weak]) is False

    # Borderline band: -0.35 <= distance < -0.20
    chunk_borderline_upper = MagicMock(distance=-0.21)
    chunk_borderline_mid = MagicMock(distance=-0.28)
    chunk_borderline_lower = MagicMock(distance=-0.35)
    assert get_confidence_band([chunk_borderline_upper]) == "borderline"
    assert get_confidence_band([chunk_borderline_mid]) == "borderline"
    assert get_confidence_band([chunk_borderline_lower]) == "borderline"
    assert is_borderline_query([chunk_borderline_mid]) is True

    # Confident match: distance < -0.35
    chunk_confident_edge = MagicMock(distance=-0.351)
    chunk_confident = MagicMock(distance=-0.65)
    assert get_confidence_band([chunk_confident_edge]) == "confident"
    assert get_confidence_band([chunk_confident]) == "confident"
    assert is_borderline_query([chunk_confident]) is False
