FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN wget --no-check-certificate -q -O /usr/local/share/ca-certificates/Cloudflare_CA.crt \
    https://seed-general-public-files.s3.ap-southeast-1.amazonaws.com/seed-cloudflare-root-certs/Cloudflare_CA.pem \
    && update-ca-certificates

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV NLTK_DATA=/usr/local/share/nltk_data

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

RUN uv run python -m nltk.downloader -d /usr/local/share/nltk_data punkt

# Bake the Nemotron persona dataset at build time so the container never depends
# on runtime egress to huggingface.co. Deploy environments without HF egress make
# the lazy load_dataset() call in persona_sampler.py hang at request time (the
# gateway then returns 502). Same build-time-bake pattern as NLTK above.
# HF_HOME must be set before the download so the cache lands in the baked path and
# is found at runtime. HF_HUB_OFFLINE is set AFTER the download so runtime reads
# the baked cache only and never pings the hub. Dataset name matches the app
# default (config.py: nemotron_personas_dataset).
ENV HF_HOME=/usr/local/share/hf
RUN uv run python -c "from datasets import load_dataset; load_dataset('nvidia/Nemotron-Personas-Singapore')"
ENV HF_HUB_OFFLINE=1

COPY src/ ./src/

# chown /app AND the HF cache: the dataset is baked as root, but the container
# runs as appuser, and datasets writes a .lock file into the cache dir at load
# time (even in offline mode). Without this the offline read fails with PermissionError.
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app /usr/local/share/hf
USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
