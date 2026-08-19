# Tackety - single-image deployment for the FastAPI engine + demo UI.
#
# Build:  docker build -t tackety .
# Run:    docker run -p 8000:8000 -v tackety_data:/app/engine/data --env-file engine/.env tackety
# (docker-compose.yml wraps this with the volume/env-file wiring already done)

FROM python:3.10-slim AS base

# sqlite-vec ships a compiled extension; sentence-transformers/torch need a
# working C toolchain to build a couple of their own transitive deps on
# some platforms. Kept in one layer, removed from the final image isn't
# done here since python:slim has no easy multi-stage split for compiled
# extension loading at runtime - this is a deliberate simplicity-over-size
# tradeoff appropriate for a self-hosted single-container deploy.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so this layer caches across code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine/ ./engine/
COPY demo/ ./demo/

# Pre-download the sentence-transformer model at build time instead of on
# first request - avoids a slow, network-dependent first startup and lets
# the container run fully offline afterward.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Data directory is a mount point (see docker-compose.yml) - created here
# so it exists with correct permissions even if the volume is empty.
RUN mkdir -p /app/engine/data

EXPOSE 8000

# Not run as root by default is a reasonable hardening step for anything
# that ends up internet-facing.
RUN useradd --create-home --shell /bin/bash tackety \
    && chown -R tackety:tackety /app
USER tackety

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

WORKDIR /app/engine
CMD ["python", "api.py"]
