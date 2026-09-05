import json
import logging
import math

import groq
from celery import chord, group, shared_task
from django.db import transaction
from pydantic import BaseModel, ConfigDict
from pydantic import ValidationError as PydanticValidationError

from jobs import groq_client
from jobs.models import Application, Job, Resume, ResumeChunk
from jobs.services.chunking import chunk_text
from jobs.services.embedding import embed_chunks, embed_text
from jobs.services.extraction import extract_text
from jobs.services.extraction_llm import extract_skills_experience
from jobs.services.retrieval import aggregate_top2_mean, fetch_candidate_chunks
from jobs.services.scoring import score_application

logger = logging.getLogger(__name__)


@shared_task
def process_resume(resume_id):
    """Extracts text from resume, chunks it, embeds each chunk, and saves the chunks in a separate table"""
    try:
        resume = Resume.objects.get(id=resume_id)
        resume.status = Resume.Status.PROCESSING
        resume.save(update_fields=["status"])

        resume_text: str = extract_text(resume.file.path)
        resume.full_text = resume_text
        resume.save(update_fields=["full_text"])

        resume_chunks_texts = chunk_text(resume_text)
        resume_embeddings = embed_chunks(resume_chunks_texts)

        resume_chunks_instance = [
            ResumeChunk(
                resume=resume,
                chunk_text=chunk_str,
                embedding=embedding,
                chunk_index=chunk_index,
            )
            for chunk_index, (chunk_str, embedding) in enumerate(
                zip(resume_chunks_texts, resume_embeddings)
            )
        ]
        with transaction.atomic():
            ResumeChunk.objects.bulk_create(resume_chunks_instance)
            resume.status = Resume.Status.DONE
            resume.save(update_fields=["status"])
    except Exception as exc:
        logger.exception("Failed to process resume ID %s: %s", resume_id, exc)
        Resume.objects.filter(id=resume_id).update(status=Resume.Status.FAILED)
        raise exc


@shared_task
def embed_job(job_id):
    """Embeds the job at creation. No chunking for job"""
    try:
        job = Job.objects.get(id=job_id)
        job_description = job.description
        job_embedding: list[float] = embed_text(job_description)
        job.embedding = job_embedding
        job.save(update_fields=["embedding"])
    except Exception as exc:
        raise exc


@shared_task
def recompute_job_rankings(job_id, multiplier: int = 5):
    """gets the top chunks with multiplier, saves the retrieval score for 2X and makes a profile for the exact head_count"""
    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        logger.error("Job with id %s does not exist.", job_id)
        return

    job.ranking_status = Job.RankingStatus.COMPUTING
    job.save(update_fields=["ranking_status"])

    try:
        chunks = fetch_candidate_chunks(job, multiplier=multiplier)
        ranked = aggregate_top2_mean(chunks)
        score_by_resume = dict(ranked)

        all_applications = Application.objects.filter(job=job)
        to_update = []
        for app in all_applications:
            app.retrieval_score = score_by_resume.get(
                app.resume_id
            )  # None if not in this round's fetch
            to_update.append(app)

        with transaction.atomic():
            Application.objects.bulk_update(to_update, ["retrieval_score"])
            job.ranking_status = Job.RankingStatus.RETRIEVAL_DONE
            job.save(update_fields=["ranking_status"])

        extraction_candidates = ranked[: math.floor(job.head_count * 2)]
        needs_extraction = [
            resume_id
            for resume_id, _ in extraction_candidates
            if not Resume.objects.get(id=resume_id).skills
        ]

        chord(group(extract_resume_profile.s(rid) for rid in needs_extraction))(
            finalize_scoring.s(job.id)
        )

    except Exception as exc:
        logger.exception("Ranking failed for job %s: %s", job_id, exc)
        job.ranking_status = Job.RankingStatus.FAILED
        job.save(update_fields=["ranking_status"])
        raise exc


@shared_task(
    autoretry_for=(
        groq.APIConnectionError,
        groq.RateLimitError,
        groq.InternalServerError,
    ),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 5},
)
def extract_resume_profile(resume_id):
    """Extracts skills and experience from resumes and updates the skills and experience_years field"""
    SYSTEM_PROMPT = (
        "You are a resume parser. Extract only skills and experience explicitly "
        "stated or directly inferable from dates in the text. Do not invent "
        "skills that are not named. If total years of professional experience "
        "cannot be determined from the text, return null for experience_years "
        "rather than guessing a number."
    )
    try:
        resume = Resume.objects.get(id=resume_id)
    except Resume.DoesNotExist:
        logger.error("Resume %s does not exist. Skipping extraction.", resume_id)
        return
    if resume.skills is not None:
        logger.info(
            "Resume %s already has extracted skills. Skipping LLM call.", resume_id
        )
        return

    if not resume.full_text:
        logger.warning(
            "Resume %s has no full_text extracted. Cannot run LLM parser.", resume_id
        )
        return
    try:
        extracted_profile = extract_skills_experience(SYSTEM_PROMPT, resume.full_text)
        resume.skills = extracted_profile.skills
        resume.experience_years = extracted_profile.experience_years
        resume.save(update_fields=["skills", "experience_years"])
    except PydanticValidationError as val_err:
        # Schema validation error: Fail fast (retrying with identical prompt won't fix bad JSON)
        logger.error("Pydantic validation failed for resume %s: %s", resume_id, val_err)
        # Do not raise val_err so Celery doesn't waste retries on unparseable data
        return


@shared_task(
    autoretry_for=(
        groq.APIConnectionError,
        groq.RateLimitError,
        groq.InternalServerError,
    ),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 5},
)
def extract_job_profile(job_id):
    """Extracts skills and experiene for a job and updates the table"""
    SYSTEM_PROMPT = (
        "You are a job description parser. Extract only skills, tools, and qualifications "
        "explicitly stated as required or preferred in the text. Do not invent skills "
        "that are not named. Extract the minimum required years of professional experience "
        "as an integer. If the minimum required years of experience cannot be determined "
        "from the text, return null for experience_years rather than guessing a number."
    )
    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        logger.error("Job %s does not exist. Skipping extraction.", job_id)
        return
    if job.skills is not None:
        logger.info("Job %s already has extracted skills. Skipping LLM call.", job_id)
        return
    if not job.description:
        logger.warning(
            "Job %s has no full_text extracted. Cannot run LLM parser.", job_id
        )
        return
    try:
        extracted_profile = extract_skills_experience(SYSTEM_PROMPT, job.description)
        job.skills = extracted_profile.skills

        # Only overwrite required_experience_years if the user left it empty (None)
        if (
            job.required_experience_years is None
            and extracted_profile.experience_years is not None
        ):
            job.required_experience_years = extracted_profile.experience_years
            job.save(update_fields=["skills", "required_experience_years"])
        else:
            job.save(update_fields=["skills"])
    except PydanticValidationError as val_err:
        # Schema validation error: Fail fast (retrying with identical prompt won't fix bad JSON)
        logger.error("Pydantic validation failed for job %s: %s", job_id, val_err)
        # Do not raise val_err so Celery doesn't waste retries on unparseable data
        return


@shared_task
def finalize_scoring(*args, job_id=None):
    """Chord callback — runs after all extract_resume_profile tasks in the group finish.
    Loops applications for job, calls score_application, trims to head_count,
    sets ranking_status = DONE."""
    if job_id is None and args:
        job_id = args[-1]

    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        logger.error("Job %s does not exist. Aborting finalize_scoring.", job_id)
        return

    applications = Application.objects.filter(job=job).select_related("resume", "job")

    for application in applications:
        if application.final_score is not None:
            logger.info("Application %s already has final score", application.id)
            continue  # already scored in a prior recompute — never touch it again
        if application.retrieval_score is None:
            continue  # fell outside this recompute's fetch window
        if application.resume.skills is None:
            continue  # extraction failed/never ran — no data to score against

        normalized_retrieval_score = -application.retrieval_score
        score_application(application, normalized_retrieval_score)

    job.ranking_status = Job.RankingStatus.DONE
    job.save(update_fields=["ranking_status"])

    scored_applications = Application.objects.filter(
        job=job, final_score__isnull=False
    ).order_by("-final_score")[: job.head_count]
    group(
        generate_application_profile_task.s(app.id) for app in scored_applications
    ).apply_async()


class LLM_Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    strengths: list[str]
    gaps: list[str]


PROFILE_SYSTEM_PROMPT = (
    "You are writing a hiring summary for a recruiter based on pre-computed "
    "match data. Do not invent skills, experience, or scores not given to you. "
    "The final_score is a weighted composite, not a percentage — do not describe "
    "it as a percentage. Write the summary in a neutral, factual tone."
)


def _build_profile_user_prompt(
    resume_skills,
    job_skills,
    resume_exp_years,
    job_req_years,
    retrieval_score,
    final_score,
) -> str:
    matched = sorted(
        set(s.lower() for s in resume_skills) & set(s.lower() for s in job_skills)
    )
    missing = sorted(
        set(s.lower() for s in job_skills) - set(s.lower() for s in resume_skills)
    )
    return (
        f"Candidate skills: {resume_skills}\n"
        f"Required skills: {job_skills}\n"
        f"Matched skills: {matched}\n"
        f"Missing skills: {missing}\n"
        f"Candidate years of experience: {resume_exp_years}\n"
        f"Required years of experience: {job_req_years}\n"
        f"Vector similarity to job description (range -1 to 1): {retrieval_score}\n"
        f"Final weighted match score: {final_score}\n\n"
        "Write a short summary, a list of strengths, and a list of gaps."
    )


@shared_task(
    autoretry_for=(
        groq.APIConnectionError,
        groq.RateLimitError,
        groq.InternalServerError,
    ),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 5},
)
def generate_application_profile_task(application_id):
    """builds a profile for the exact head_count, using all the information so far from applications process"""
    try:
        application = Application.objects.select_related("resume", "job").get(
            id=application_id
        )
    except Application.DoesNotExist:
        logger.error(
            "Application %s does not exist. Skipping profile generation.",
            application_id,
        )
        return
    if application.llm_profile:
        logger.info(
            "Application %s already has llm profile. Skipping profile generation.",
            application_id,
        )
        return

    client = groq_client.groq_client_instance
    resume_skills = application.resume.skills
    job_skills = application.job.skills
    job_req_years = application.job.required_experience_years
    resume_exp_years = application.resume.experience_years
    retrieval_score = -application.retrieval_score
    final_score = application.final_score

    user_content = _build_profile_user_prompt(
        resume_skills,
        job_skills,
        resume_exp_years,
        job_req_years,
        retrieval_score,
        final_score,
    )
    try:
        llm_response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": PROFILE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "llm_profile_builder",
                    "strict": True,
                    "schema": LLM_Profile.model_json_schema(),
                },
            },
        )
        raw_result = json.loads(llm_response.choices[0].message.content or "{}")
        result = LLM_Profile.model_validate(raw_result)
    except PydanticValidationError as val_err:
        logger.error(
            "Pydantic validation failed for application %s: %s", application_id, val_err
        )
        return
    application.llm_profile = result.model_dump()
    application.save(update_fields=["llm_profile"])
