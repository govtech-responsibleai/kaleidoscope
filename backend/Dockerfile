# Dockerfile for Kaleidoscope API

FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install SSL certs for Cloudflare
RUN wget --no-check-certificate -q -O /usr/local/share/ca-certificates/Cloudflare_CA.crt \
https://seed-general-public-files.s3.ap-southeast-1.amazonaws.com/seed-cloudflare-root-certs/Cloudflare_CA.pem \
&& update-ca-certificates

# Set SSL cert path for httpx
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV NLTK_DATA=/usr/local/share/nltk_data

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m nltk.downloader -d /usr/local/share/nltk_data punkt

# Copy application code
COPY src/ ./src/
COPY tests/ ./tests/
COPY pytest.ini .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run the main API
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
