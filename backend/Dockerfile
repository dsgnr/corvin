# Build stage
FROM python:3.13-alpine AS builder

WORKDIR /app

# uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml uv.lock ./

RUN uv pip install \
    --prefix=/install \
    --no-cache \
    -r <(uv export --frozen --no-dev)

# Runtime stage
FROM python:3.13-alpine AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apk add --no-cache ffmpeg deno tzdata

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--worker-class", "gevent", "--worker-connections", "100", "--timeout", "120", "--access-logfile", "-", "--capture-output", "run:app"]

HEALTHCHECK --interval=15s --timeout=10s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://0.0.0.0:5000/api/tasks/stats || exit 1
