# ClearPort backend — FastAPI + the agent loop. Runs fully offline by default
# (all external dependencies have deterministic fallbacks), so the image boots
# with zero secrets and can be progressively upgraded with real credentials.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# TLS roots for outbound HTTPS — the live USITC HTS tariff API and the npm
# registry both need a CA bundle, which the slim base image omits.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install the uv package manager for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Node 20 for the @arizeai/phoenix-mcp server (the *active* half of the Arize
# integration, launched on demand via npx for three uses: the startup MCP
# handshake, the ADK agent toolset, and the on-demand /api/investigate read-back
# of a run's verify-span annotations). The per-call recovery hot path stays on
# the in-process arize-phoenix-client (no npx), so request latency is unaffected.
# Copied from the official slim image to keep the Python base small, then the MCP
# package is pre-warmed so the first investigate call does not pay the npx cost.
COPY --from=node:20-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:20-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install -g @arizeai/phoenix-mcp@latest

# Resolve dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY clearport ./clearport
RUN uv pip install --system --no-cache .

# Cloud Run injects $PORT; the entrypoint honours it (defaults to 8080).
ENV PORT=8080
EXPOSE 8080
CMD ["clearport-api"]
