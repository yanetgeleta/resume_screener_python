import logging

from celery import shared_task
from django.db import transaction

from jobs.models import Resume, ResumeChunk
from jobs.services.chunking import chunk_text
from jobs.services.embedding import embed_chunks
from jobs.services.extraction import extract_text

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
