# Backend Service - Resume Screener AI

This directory contains the Django REST Framework backend service, Celery asynchronous workers, and AI screening pipeline for the Resume Screener application.

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
uv run python manage.py runserver

# Run tests
uv run pytest
```
