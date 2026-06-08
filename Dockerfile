# ClearPort backend — FastAPI + the agent loop. Runs fully offline by default
# (all external dependencies have deterministic fallbacks), so the image boots
# with zero secrets and can be progressively upgraded with real credentials.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the uv package manager for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Resolve dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY clearport ./clearport
RUN uv pip install --system --no-cache .

# Cloud Run injects $PORT; the entrypoint honours it (defaults to 8080).
ENV PORT=8080
EXPOSE 8080
CMD ["clearport-api"]
