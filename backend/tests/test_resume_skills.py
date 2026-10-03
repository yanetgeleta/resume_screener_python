import pytest
from jobs.tasks import extract_resume_profile

from tests.factories import NoneSkillsResumeFactory, SkillsResumeFactory


@pytest.mark.django_db
def test_none_skills_resume_factory(mock_groq_client_extraction):
    resume = NoneSkillsResumeFactory()

    extract_resume_profile(resume.id)
    mock_groq_client_extraction.chat.completions.create.assert_called_once()
    resume.refresh_from_db()
    assert resume.skills is not None


@pytest.mark.django_db
def test_skills_resume_factory(mock_groq_client_extraction):
    resume = SkillsResumeFactory()

    extract_resume_profile(resume.id)
    mock_groq_client_extraction.chat.completions.create.assert_not_called()


@pytest.mark.django_db
def test_extract_resume_profile_rate_limit_error_bubbles_up(mocker):
    import groq
    import httpx

    resume = NoneSkillsResumeFactory()
    req = httpx.Request("POST", "https://api.groq.com")
    resp = httpx.Response(429, request=req)
    rate_limit_exc = groq.RateLimitError(
        "Rate limit exceeded", response=resp, body=None
    )

    mocker.patch("jobs.tasks.extract_skills_experience", side_effect=rate_limit_exc)

    with pytest.raises(groq.RateLimitError):
        extract_resume_profile(resume.id)

    resume.refresh_from_db()
    # Skills should NOT be set to [] on RateLimitError, so Celery retry can re-attempt
    assert resume.skills is None


@pytest.mark.django_db
def test_extract_resume_profile_bad_request_error_falls_back_to_empty_skills(mocker):
    import groq
    import httpx

    resume = NoneSkillsResumeFactory()
    req = httpx.Request("POST", "https://api.groq.com")
    resp = httpx.Response(400, request=req)
    bad_req_exc = groq.BadRequestError("Bad Request", response=resp, body=None)

    mocker.patch("jobs.tasks.extract_skills_experience", side_effect=bad_req_exc)

    # Should not raise exception
    extract_resume_profile(resume.id)

    resume.refresh_from_db()
    assert resume.skills == []
