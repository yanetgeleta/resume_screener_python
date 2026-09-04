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
