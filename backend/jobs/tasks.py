import logging
import math

import groq
from celery import chord, group, shared_task
from django.db import transaction
from pydantic import ValidationError as PydanticValidationError

from backend.jobs.services.extraction_llm import extract_skills_experience
from backend.jobs.services.scoring import score_application
from jobs.models import Application, Job, Resume, ResumeChunk
from jobs.services.chunking import chunk_text
from jobs.services.embedding import embed_chunks, embed_text
from jobs.services.extraction import extract_text
from jobs.services.retrieval import aggregate_top2_mean, fetch_candidate_chunks

logger = logging.getLogger(__name__)


@shared_task
def process_resume(resume_id):
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
def finalize_scoring(_, job_id):
    """Chord callback — runs after all extract_resume_profile tasks in the group finish.
    Loops applications for job, calls score_application, trims to head_count,
    sets ranking_status = DONE."""
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
