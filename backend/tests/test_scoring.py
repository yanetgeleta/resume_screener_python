import pytest
from jobs.services.scoring import compute_skill_score, compute_years_score


@pytest.mark.parametrize(
    "actual_years, required_years, expected",
    [(1, 2, 0.5), (2, 2, 1), (4, 2, 1), (4, None, 1)],
)
def test_compute_years_score(actual_years, required_years, expected):

    assert compute_years_score(actual_years, required_years) == pytest.approx(expected)


@pytest.mark.parametrize(
    "resume_skills, job_skills, expected",
    [
        (["python", "javascript"], None, 1),
        (None, ["python", "javascript"], 0),
        (
            ["python", "javascript"],
            ["python", "javascript", "docker", "kubernetes"],
            0.5,
        ),
        (["python", "javascript", "docker", "kubernetes"], ["python", "javascript"], 1),
        (None, None, 1),
    ],
)
def test_compute_skill_score(resume_skills, job_skills, expected):
    assert compute_skill_score(resume_skills, job_skills) == pytest.approx(expected)
