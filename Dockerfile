# RFSN Hybrid Engine
FROM python:3.11-slim

LABEL maintainer="dawsonblock"
LABEL version="0.5.2"
LABEL description="RFSN NPC Dialogue Engine with local LLM inference"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[api]"

# Copy application code
COPY rfsn_hybrid/ ./rfsn_hybrid/
COPY version.json ./

# Create directories for data persistence
RUN mkdir -p /app/data /app/models

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV RFSN_DATA_DIR=/app/data
ENV RFSN_LOG_LEVEL=INFO

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from rfsn_hybrid.health import run_health_checks; h = run_health_checks(); exit(0 if h.healthy else 1)"

# Default command: run API server
CMD ["python", "-m", "rfsn_hybrid.api", "--host", "0.0.0.0", "--port", "8000"]
