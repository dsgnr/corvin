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

COPY pyproject.toml poetry.lock* ./

RUN poetry install --only=main --no-root --no-cache

# Runtime stage
FROM python:3.13-alpine AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/.venv/lib/python3.13/site-packages"

RUN apk add --no-cache ffmpeg curl

# Install Deno
RUN curl -fsSL https://deno.land/install.sh | sh
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

WORKDIR /app

COPY --from=builder $PYTHONPATH $PYTHONPATH

COPY . .

EXPOSE 5000
CMD ["python", "run.py"]
