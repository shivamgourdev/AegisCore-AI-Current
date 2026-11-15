# Stage 1: Build stage - install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime stage - minimal image
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create non-root user for security
RUN groupadd -r aegiscore && useradd -r -g aegiscore aegiscore

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY backend/app ./backend/app
COPY backend/tests ./backend/tests
COPY scripts ./scripts
COPY pyproject.toml ./
COPY requirements.txt ./

# Set environment variables
ENV AEGISCORE_DATA_DIR=/data
ENV AEGISCORE_OLLAMA_URL=http://host.docker.internal:11434
ENV AEGISCORE_CHAT_MODEL=phi3.5:3.8b
ENV AEGISCORE_EMBEDDING_MODEL=nomic-embed-text:latest
ENV PYTHONPATH=/app/backend/app
ENV PYTHONUNBUFFERED=1

# Create data directory
RUN mkdir -p /data && chown -R aegiscore:aegiscore /data

# Create non-root user and set ownership
RUN chown -R aegiscore:aegiscore /app
USER aegiscore

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://127.0.0.1:8000/health', timeout=5)" || exit 1

# Start the application
CMD ["python", "-m", "uvicorn", "aegiscore.main:app", "--host", "0.0.0.0", "--port", "8000"]
