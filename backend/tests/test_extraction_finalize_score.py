import pytest
from celery import chord, group
from jobs.models import Job
from jobs.tasks import extract_resume_profile, finalize_scoring

from tests.factories import ApplicationFactory, JobFactory, NoneSkillsResumeFactory


@pytest.mark.django_db(transaction=True)
def test_chord_extraction_then_finalize_scoring(celery_worker, mock_groq_client_dual):
    # 1. Setup tenant-consistent job and resumes
    job = JobFactory(head_count=2)
    resumes = [NoneSkillsResumeFactory(company=job.company) for _ in range(3)]

    applications = [
        ApplicationFactory(job=job, resume=r, retrieval_score=-0.1 * i)
        for i, r in enumerate(resumes)
    ]

    # 2. Trigger chord: .si(job.id) creates an immutable signature so Celery
    # doesn't inject the list of extract_resume_profile results into finalize_scoring
    header = group(extract_resume_profile.s(r.id) for r in resumes)
    callback = finalize_scoring.si(job.id)

    chord_promise = chord(header)(callback)
    chord_promise.get(timeout=30)

    # 3. Assertions
    job.refresh_from_db()
    assert job.ranking_status == Job.RankingStatus.DONE

    for app in applications:
        app.refresh_from_db()
        app.resume.refresh_from_db()
        assert app.resume.skills is not None
        assert app.final_score is not None
