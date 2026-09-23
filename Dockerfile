# =========================
# Stage 1: Builder
# =========================
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# =========================
# Stage 2: Runtime
# =========================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Tesseract OCR + French/Arabic language packs
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       tesseract-ocr \
       tesseract-ocr-fra \
       tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Copy only application source code
COPY src ./src

# `src/m5_api/main.py` fait `from monitoring.instrumentation.metrics import
# instrumenter` : sans ce répertoire, l'image démarre l'ingestion M1 mais pas
# l'API. Ajouté ici plutôt que monté par docker-compose, pour que l'image
# reste exécutable seule.
COPY monitoring ./monitoring

# Create data directories without copying the corpus into the image
RUN mkdir -p data/raw data/processed

# Run the application as a non-root user
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "src.m1_ingestion.ingest", "--raw-dir", "data/raw", "--out-dir", "data/processed"]
