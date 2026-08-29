# =========================
# Stage 1: Builder
# =========================
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# =========================
# Stage 2: Runtime
# =========================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Tesseract OCR + French/Arabic language packs
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       tesseract-ocr \
       tesseract-ocr-fra \
       tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

COPY src ./src
COPY data ./data

RUN mkdir -p data/raw data/processed

CMD ["python", "-m", "src.m1_ingestion.ingest", "--raw-dir", "data/raw", "--out-dir", "data/processed"]
