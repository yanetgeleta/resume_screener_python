# Backend Service - Resume Screener AI

This directory contains the Django REST Framework backend service, Celery asynchronous workers, pgvector dense retrieval engine, and the **Multi-Tenant Interactive RAG Chat Assistant** with Server-Sent Events (SSE) streaming for the Resume Screener application.

For full architectural documentation, API references, pipeline explanations, and setup instructions, refer to the [Root README](../README.md).

## Quick Backend Commands

```bash
# Sync dependencies
uv sync --all-groups

# Run migrations
uv run python manage.py migrate

# Run Celery worker
uv run celery -A config worker --loglevel=info -c 4

# Run development server
uv run python manage.py runserver 8000

# Run all automated tests (31 tests)
uv run pytest --reuse-db

# Run Phase 6 RAG Chat Assistant tests
uv run pytest tests/test_retrieval.py \
              tests/test_chat_prefilter.py \
              tests/test_chat_prompt.py \
              tests/test_chat_stream.py \
              tests/test_chat_sessions.py \
              --reuse-db
```
