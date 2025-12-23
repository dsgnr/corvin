# Build stage
FROM python:3.13-alpine AS builder
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VER=2.2.1

WORKDIR /app

RUN apk add --no-cache gcc musl-dev libffi-dev \
    && pip install --no-cache-dir poetry==$POETRY_VER

COPY pyproject.toml poetry.lock ./

RUN poetry install --only=main --no-root --no-cache

# Runtime stage
FROM python:3.13-alpine AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

RUN apk add --no-cache ffmpeg deno

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY . .

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "run:app"]

HEALTHCHECK --interval=15s --timeout=10s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://0.0.0.0:5000/api/tasks/stats || exit 1
