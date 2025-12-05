FROM python:3.13-slim

# Install ffmpeg and clean up
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml poetry.lock* ./

# Install dependencies (no dev deps, no virtualenv in container)
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-root --no-ansi --only main

# Copy application code
COPY . .

EXPOSE 5000

CMD ["python", "run.py"]