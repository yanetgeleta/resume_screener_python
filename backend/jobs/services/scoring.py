import logging

from backend.jobs.models import Application

logger = logging.getLogger(__name__)


def score_application(
    application: Application, normalized_retrieval_score: float
) -> None:
    """Combines normalized retrieval (65%) with skill/years match (35%),
    writes application.final_score. Called from the chord callback, one per app."""
    years_score = compute_years_score(
        application.resume.experience_years, application.job.required_experience_years
    )
    skills_score = compute_skill_score(
        application.resume.skills, application.job.skills
    )
    final_score = (
        (65 * normalized_retrieval_score) + (20 * skills_score) + (15 * years_score)
    )
    application.final_score = final_score
    application.save(update_fields=["final_score"])


def compute_years_score(actual_years: int | None, required_years: int | None) -> float:
    """Returns a 0-35 value per the null/zero/ratio rules already agreed."""
    if not required_years:
        return 1
    elif actual_years is None:
        return 0
    elif actual_years >= required_years:
        return 1
    else:
        return actual_years / required_years


def compute_skill_score(
    resume_skills: list[str] | None, job_skills: list[str] | None
) -> float:
    """Matched/required ratio, naturally 0-1 (or 0-35, pick one scale and stay consistent with compute_years_score)."""
    # skills_score: float
    if not job_skills:
        return 1
    elif not resume_skills:
        return 0
    job_skill_set = {str(skill).strip().lower() for skill in job_skills}
    matched_skills = [
        resume_skill
        for resume_skill in resume_skills
        if str(resume_skill).strip().lower() in job_skill_set
    ]
    return len(matched_skills) / len(job_skills)
