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

COPY src/ ./src/

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
