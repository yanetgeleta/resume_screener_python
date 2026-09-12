import pytest
from jobs.services.retrieval import (
    fetch_candidate_chunks,
    fetch_candidate_chunks_for_session,
    retrieve_for_session,
)

from tests.factories import (
    ApplicationFactory,
    ChatSessionFactory,
    CompanyFactory,
    JobFactory,
    ResumeChunkFactory,
    ResumeFactory,
)


@pytest.fixture
def dummy_vector():
    v = [1.0 / (384**0.5)] * 384
    return v


@pytest.mark.django_db
def test_fetch_candidate_chunks_for_session_basic(mocker, dummy_vector):
    mocker.patch("jobs.services.retrieval.embed_text", return_value=dummy_vector)

    # Setup job and session
    company = CompanyFactory()
    job = JobFactory(company=company, head_count=2)
    session = ChatSessionFactory(company=company, job=job)

    # Resumes applied to this job
    resume1 = ResumeFactory(company=company)
    resume2 = ResumeFactory(company=company)
    ApplicationFactory(job=job, resume=resume1)
    ApplicationFactory(job=job, resume=resume2)

    # Chunks with dummy embeddings
    v1 = dummy_vector
    v2 = [-x for x in dummy_vector]

    c1 = ResumeChunkFactory(resume=resume1, chunk_text="Chunk 1", embedding=v1)
    c2 = ResumeChunkFactory(resume=resume2, chunk_text="Chunk 2", embedding=v2)

    chunks = fetch_candidate_chunks_for_session(session, query="Find developer")

    assert len(chunks) == 2
    # c1 has inner product ~ 1.0 -> MaxInnerProduct ~ -1.0 (closer/smaller)
    # c2 has inner product ~ -1.0 -> MaxInnerProduct ~ 1.0 (further/larger)
    assert chunks[0].id == c1.id
    assert chunks[0].distance < chunks[1].distance
    assert hasattr(chunks[0], "distance")
    assert chunks[0].resume == resume1


@pytest.mark.django_db
def test_job_and_tenant_isolation_at_query_level(mocker, dummy_vector):
    """
    Ensure chunks from another job (even within the same company)
    and chunks from another company are strictly filtered out at the query level.
    """
    mocker.patch("jobs.services.retrieval.embed_text", return_value=dummy_vector)

    company_a = CompanyFactory()
    company_b = CompanyFactory()

    job_a1 = JobFactory(company=company_a, head_count=2)
    job_a2 = JobFactory(company=company_a, head_count=2)
    job_b = JobFactory(company=company_b, head_count=2)

    session_a1 = ChatSessionFactory(company=company_a, job=job_a1)

    # Resume 1 applied to Job A1 (target)
    r1 = ResumeFactory(company=company_a)
    ApplicationFactory(job=job_a1, resume=r1)
    c1 = ResumeChunkFactory(
        resume=r1, chunk_text="Target chunk A1", embedding=dummy_vector
    )

    # Resume 2 applied to Job A2 (same company, different job)
    r2 = ResumeFactory(company=company_a)
    ApplicationFactory(job=job_a2, resume=r2)
    c2 = ResumeChunkFactory(
        resume=r2, chunk_text="Other job chunk A2", embedding=dummy_vector
    )

    # Resume 3 applied to Job B (different company, different job)
    r3 = ResumeFactory(company=company_b)
    ApplicationFactory(job=job_b, resume=r3)
    c3 = ResumeChunkFactory(
        resume=r3, chunk_text="Tenant B chunk", embedding=dummy_vector
    )

    # Query scoped to session_a1
    chunks = fetch_candidate_chunks_for_session(session_a1, query="test query")

    chunk_ids = [c.id for c in chunks]
    assert c1.id in chunk_ids
    assert c2.id not in chunk_ids
    assert c3.id not in chunk_ids


@pytest.mark.django_db
def test_cross_company_session_job_mismatch_blocks_leak(mocker, dummy_vector):
    """
    If a session has company B but references job A, query-level isolation
    ensures zero chunks from job A leak to company B.
    """
    mocker.patch("jobs.services.retrieval.embed_text", return_value=dummy_vector)

    company_a = CompanyFactory()
    company_b = CompanyFactory()

    job_a = JobFactory(company=company_a)
    r_a = ResumeFactory(company=company_a)
    ApplicationFactory(job=job_a, resume=r_a)
    ResumeChunkFactory(
        resume=r_a, chunk_text="Company A secret chunk", embedding=dummy_vector
    )

    # Tampered session: owned by company B but pointing to company A's job
    tampered_session = ChatSessionFactory(company=company_b, job=job_a)

    chunks = fetch_candidate_chunks_for_session(tampered_session, query="secret")
    assert len(chunks) == 0


@pytest.mark.django_db
def test_retrieve_for_session_reuses_aggregate_top2_mean(mocker, dummy_vector):
    mocker.patch("jobs.services.retrieval.embed_text", return_value=dummy_vector)

    company = CompanyFactory()
    job = JobFactory(company=company, head_count=2)
    session = ChatSessionFactory(company=company, job=job)

    r1 = ResumeFactory(company=company)
    ApplicationFactory(job=job, resume=r1)

    c1 = ResumeChunkFactory(resume=r1, chunk_index=0, embedding=dummy_vector)
    c2 = ResumeChunkFactory(resume=r1, chunk_index=1, embedding=dummy_vector)

    # Test unpacking and properties
    chunks, ranked = retrieve_for_session(session, query="search candidate")

    assert len(chunks) == 2
    assert len(ranked) == 1
    resume_id, mean_distance = ranked[0]
    assert resume_id == r1.id
    assert isinstance(mean_distance, float)

    # Test named properties on result object
    result = retrieve_for_session(session, query="search candidate")
    assert result.chunks == chunks
    assert result.ranked == ranked


@pytest.mark.django_db
def test_fetch_candidate_chunks_backward_compatibility(mocker, dummy_vector):
    mocker.patch("jobs.services.retrieval.embed_text", return_value=dummy_vector)

    company = CompanyFactory()
    job = JobFactory(company=company, head_count=2)
    job.embedding = dummy_vector
    job.save()

    r1 = ResumeFactory(company=company)
    ApplicationFactory(job=job, resume=r1)
    c1 = ResumeChunkFactory(resume=r1, embedding=dummy_vector)

    # 1. Original signature without query
    orig_chunks = fetch_candidate_chunks(job)
    assert len(orig_chunks) == 1
    assert orig_chunks[0].id == c1.id

    # 2. Signature with query
    query_chunks = fetch_candidate_chunks(job, query="Find engineer")
    assert len(query_chunks) == 1
    assert query_chunks[0].id == c1.id
