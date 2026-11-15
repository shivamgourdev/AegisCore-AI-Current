# AegisCore AI — Deployment Guide

**Project:** C:\Users\shiva\OneDrive\Desktop\AegisCore-AI
**Version:** 1.0.0
**Date:** 2026-11-09

This document describes how to deploy AegisCore AI in production using Docker and Docker Compose.

---

## 1. Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Ollama running locally or accessible via network
- At least 4GB RAM available
- At least 10GB disk space

---

## 2. Quick Start

### 2.1 Clone and Configure

```bash
cd /path/to/AegisCore-AI
cp .env.example .env  # Create environment file
# Edit .env with your configuration
```

### 2.2 Start All Services

```bash
docker-compose up -d
```

This starts:
- **AegisCore AI Backend** on port 8000
- **Ollama** on port 11434

### 2.3 Verify Deployment

```bash
# Check backend health
curl http://localhost:8000/health

# Check Ollama health
curl http://localhost:11434/api/tags

# View logs
docker-compose logs -f
```

### 2.4 Access the Frontend

Open `http://localhost:5500` in your browser (requires frontend server running separately).

---

## 3. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AEGISCORE_DATA_DIR` | `/data` | Directory for SQLite database and uploads |
| `AEGISCORE_OLLAMA_URL` | `http://ollama:11434` | Ollama API endpoint |
| `AEGISCORE_CHAT_MODEL` | `phi3.5:3.8b` | Generation model |
| `AEGISCORE_EMBEDDING_MODEL` | `nomic-embed-text:latest` | Embedding model |
| `PYTHONPATH` | `/app/backend/app` | Python module path |
| `PYTHONUNBUFFERED` | `1` | Disable Python output buffering |

---

## 4. Data Persistence

| Volume | Path | Contents |
|--------|------|----------|
| `aegiscore-data` | `/data` | SQLite database, extracted text, chunks, embeddings |
| `ollama-data` | `/root/.ollama` | Ollama models and configuration |

Data persists across container restarts via Docker named volumes.

---

## 5. Health Checks

### Backend Health

```bash
curl http://localhost:8000/health
```

Returns:
```json
{
  "status": "ok",
  "service": "aegiscore-api",
  "version": "1.0.0",
  "ollama": "healthy"
}
```

### Ollama Health

```bash
curl http://localhost:11434/api/tags
```

---

## 6. Logging

Application logs are structured JSON and output to stdout. They can be captured via:

```bash
docker-compose logs -f aegiscore-backend
```

Log fields include: timestamp, level, logger, message, module, function, line.

---

## 7. Restart and Recovery

### Restart Services

```bash
docker-compose restart
```

### Restart Single Service

```bash
docker-compose restart aegiscore-backend
```

### Full Reset (Warning: Deletes Data)

```bash
docker-compose down -v
docker-compose up -d
```

---

## 8. Scaling

The backend is stateless (except for SQLite data in the volume). To scale:

1. Increase `aegiscore-backend` replica count in docker-compose.yml
2. Ensure `AEGISCORE_DATA_DIR` points to shared storage
3. Configure a load balancer in front of multiple instances

---

## 9. Troubleshooting

### Backend Won't Start

```bash
# Check logs
docker-compose logs aegiscore-backend

# Verify Ollama is reachable
curl http://localhost:11434/api/tags

# Check environment variables
docker-compose exec aegiscore-backend env | grep AEGISCORE
```

### Ollama Not Ready

```bash
# Check Ollama logs
docker-compose logs ollama

# Wait for Ollama to be ready
docker-compose logs -f ollama
```

### High Memory Usage

Reduce Ollama model size or limit concurrent requests:
```bash
# In docker-compose.yml, add to aegiscore-backend environment:
- OLLAMA_MAX_QUEUE=5
```

---

## 10. Security Notes

- Backend runs as non-root user (`aegiscore`)
- No secrets hardcoded in Dockerfile
- All configuration via environment variables
- File upload size limited to 10 MB
- Only PDF, TXT, MD files accepted
