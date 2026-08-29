from collections import defaultdict

from pgvector.django import MaxInnerProduct

from jobs.models import ResumeChunk


def fetch_candidate_chunks(job, multiplier: int = 10):
    """
    Over-fetch resume chunks for a job, tenant-scoped through
    Resume -> Application -> Job. Ordered by MaxInnerProduct distance
    (smaller = more similar, per pgvector's negation convention).
    """
    over_fetch_n = job.head_count * multiplier
    return list(
        ResumeChunk.objects.filter(resume__applications__job=job)
        .annotate(distance=MaxInnerProduct("embedding", job.embedding))
        .order_by("distance")[:over_fetch_n]
        .select_related("resume")
    )


def aggregate_top2_mean(chunks) -> list[tuple[int, float]]:
    """
    Collapse chunk-level hits to one score per resume_id, using the
    mean of each resume's best 2 chunk distances. Returns
    [(resume_id, score), ...] sorted ascending (best match first).
    """
    by_resume: dict[int, list[float]] = defaultdict(list)
    for chunk in chunks:
        by_resume[chunk.resume_id].append(chunk.distance)

    scored = []
    for resume_id, distances in by_resume.items():
        distances.sort()
        top2 = distances[:2]
        scored.append((resume_id, sum(top2) / len(top2)))

    scored.sort(key=lambda pair: pair[1])
    return scored
