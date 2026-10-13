# ── Base ──
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_FROZEN=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# uv : même version qu'en CI (D012)
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

RUN addgroup --system --gid 1001 app && \
    adduser --system --uid 1001 --ingroup app app

# ── Développement ──
FROM base AS dev

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen && chown -R app:app /opt/venv

COPY --chown=app:app . .
USER app
EXPOSE 8000

# ── Production ──
FROM base AS prod

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev && chown -R app:app /opt/venv

COPY --chown=app:app . .
USER app
EXPOSE 8000

# 1 worker (D013) ; --forwarded-allow-ips à restreindre au réseau du proxy en production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips=127.0.0.1"]
