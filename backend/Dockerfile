FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_NO_DEV=1

# build essentials in case the os doesn't have c/c++ compiler for some of the libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project --no-cache

COPY . .

RUN uv sync --frozen --no-cache

FROM python:3.13-slim AS runtime

RUN groupadd --system --gid 10001 customgroup && \
    useradd --system --uid 10001 --gid customgroup --no-create-home customuser

WORKDIR /app

# COPY --from=builder /app/.venv /app/.venv

COPY --chown=customuser:customgroup --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER customuser