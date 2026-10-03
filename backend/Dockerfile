FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_NO_DEV=1 \
    UV_LINK_MODE=copy

# Build essentials for C/C++ compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./

# Step 1: Install dependencies using BuildKit persistent cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Step 2: Copy application code and install project
COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# -------------------------------------------------------------
# Runtime Stage
# -------------------------------------------------------------
FROM python:3.13-slim AS runtime

RUN groupadd --system --gid 10001 customgroup && \
    useradd --system --uid 10001 --gid customgroup --create-home --home-dir /home/customuser customuser && \
    mkdir -p /home/customuser/.cache/huggingface \
             /home/customuser/.gunicorn \
             /app/resumes \
             /app/.hf_cache && \
    chown -R customuser:customgroup /home/customuser /app/resumes /app/.hf_cache

WORKDIR /app

# Copy the built virtual environment and application code
COPY --chown=customuser:customgroup --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    HOME="/home/customuser" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER customuser