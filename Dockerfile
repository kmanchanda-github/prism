# ── Stage 1: build React UI ────────────────────────────────────────────────
FROM node:20-alpine AS ui-builder
WORKDIR /ui
COPY ui/package*.json ./
RUN npm ci --silent
COPY ui/ ./
RUN npm run build

# ── Stage 2: Python API + Celery worker ────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python deps — default provider is anthropic; override with build arg
ARG LLM_EXTRA=anthropic
COPY pyproject.toml .
RUN uv pip install --system -e ".[$LLM_EXTRA]"

COPY . .

# Copy built UI so FastAPI can serve it at /
COPY --from=ui-builder /ui/dist ./ui/dist

EXPOSE 8000
