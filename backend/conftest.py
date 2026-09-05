# conftest.py  (backend/ root, next to pyproject.toml)

import os

import numpy as np
import pytest
from django.conf import settings

os.environ.setdefault("GROQ_API_KEY", "gsk_test_mock_dummy_key_12345")

pytest_plugins = ("celery.contrib.pytest",)


@pytest.fixture
def mock_groq_client_profile(mocker):
    """
    Covers generate_application_profile_task (tasks.py).
    Canned response matches LLM_Profile schema exactly (extra="forbid").
    """
    mock_client = mocker.patch("jobs.groq_client.groq_client_instance")
    mock_response = mocker.MagicMock()
    mock_response.choices = [mocker.MagicMock()]
    mock_response.choices[0].message.content = (
        '{"summary": "Strong backend candidate with relevant experience.", '
        '"strengths": ["python", "django"], '
        '"gaps": ["no docker experience"]}'
    )
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_groq_client_extraction(mocker):
    """
    Covers extraction_llm.py's skills/experience extraction call.
    Same patch target as profile fixture — don't request both fixtures
    in the same test, the second patch will just override the first.
    """
    mock_client = mocker.patch("jobs.groq_client.groq_client_instance")
    mock_response = mocker.MagicMock()
    mock_response.choices = [mocker.MagicMock()]
    mock_response.choices[
        0
    ].message.content = '{"skills": ["python", "django"], "experience_years": 3}'
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_groq_client_dual(mocker):
    """
    For tests where both extract_resume_profile AND generate_application_profile_task
    fire in the same run (e.g. chord -> finalize_scoring -> trailing profile group).
    Picks the response shape based on which prompt was sent.
    """
    mock_client = mocker.patch("jobs.groq_client.groq_client_instance")

    def _respond(*args, **kwargs):
        messages = kwargs.get("messages", [])
        prompt_text = " ".join(m.get("content", "") for m in messages)
        response = mocker.MagicMock()
        response.choices = [mocker.MagicMock()]
        if "strengths" in prompt_text or "gaps" in prompt_text:
            response.choices[0].message.content = (
                '{"summary": "Strong backend candidate with relevant experience.", '
                '"strengths": ["python", "django"], "gaps": ["no docker experience"]}'
            )
        else:
            response.choices[
                0
            ].message.content = (
                '{"skills": ["python", "django"], "experience_years": 3}'
            )
        return response

    mock_client.chat.completions.create.side_effect = _respond
    return mock_client


@pytest.fixture
def mock_sentence_transformer(mocker):
    """
    Patches .encode() where it's CALLED: jobs/services/embedding.py
    Pre-normalized 384-dim vector — required for dot-product scoring
    to produce meaningful, reproducible numbers in tests.
    """
    normalized_vector = np.ones(384, dtype=np.float32) / np.sqrt(384)
    mock_encode = mocker.patch("jobs.services.embedding._model.encode")
    mock_encode.return_value = normalized_vector
    return mock_encode


@pytest.fixture(scope="session")
def celery_config():
    return {
        "broker_url": settings.CELERY_BROKER_URL,
        "result_backend": settings.CELERY_RESULT_BACKEND,
    }


@pytest.fixture(scope="session")
def celery_includes():
    return ["jobs.tasks"]
