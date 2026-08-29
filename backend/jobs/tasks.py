import logging

from celery import shared_task
from django.db import transaction

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
def recompute_job_rankings(job_id, multiplier: int = 10):
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

    except Exception as exc:
        logger.exception("Ranking failed for job %s: %s", job_id, exc)
        job.ranking_status = Job.RankingStatus.FAILED
        job.save(update_fields=["ranking_status"])
        raise exc
