# =============================================================================
# Stage 1: Build the React frontend
# =============================================================================
FROM node:20-slim AS frontend-builder

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
ENV VITE_API_URL=""
RUN npm run build

# =============================================================================
# Stage 2: Runtime environment (Python 3.12 + Tesseract OCR)
# =============================================================================
FROM python:3.12-slim AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    KBR_DATA_DIR=/app/data/kbr \
    INDEX_DIR=/app/data/index \
    DATABASE_URL=sqlite:////app/data/chattamai.db

# Install system dependencies:
# - tesseract-ocr & english trained data for OCR compliance checking
# - poppler-utils for PDF processing
# - curl for Docker HEALTHCHECK
# - build essentials for any native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    curl \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code and migrations
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /build/dist ./frontend/dist

# Expose API and frontend port
EXPOSE 8000

# Health check against /api/health
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
