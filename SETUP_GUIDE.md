# AegisCore AI — Setup Guide

**Project:** C:\Users\shiva\OneDrive\Desktop\AegisCore-AI
**Python:** 3.11.9
**Backend port:** 8000
**Frontend port:** 5500

## Prerequisites

1. **Windows 11**
2. **Python 3.11.9** with virtual environment at `.venv`
3. **Ollama** running locally at `http://127.0.0.1:11434`
4. **Ollama models:** `phi3.5:3.8b` and `nomic-embed-text:latest`

### Install Ollama Models

```powershell
ollama pull phi3.5:3.8b
ollama pull nomic-embed-text:latest
```

### Verify Ollama

```powershell
.venv\Scripts\python.exe -c "import httpx; r = httpx.get('http://127.0.0.1:11434/api/tags'); print(r.status_code); print(r.text)"
```

## Step 1: Activate Virtual Environment

```powershell
.venv\Scripts\Activate.ps1
```

## Step 2: Start the Backend

```powershell
# From the project root
.venv\Scripts\python.exe -m uvicorn aegiscore.main:app --host 127.0.0.1 --port 8000
```

The backend runs from the `backend/app/` directory. Use `PYTHONPATH` or run from `backend/app/`:

```powershell
cd backend/app
.venv\Scripts\python.exe -m uvicorn aegiscore.main:app --host 127.0.0.1 --port 8000
```

### Verify Backend

```powershell
.venv\Scripts\python.exe -c "import httpx; print(httpx.get('http://127.0.0.1:8000/health').status_code)"
```

Expected: `200`

## Step 3: Start the Frontend Proxy

```powershell
# From the project root
.venv\Scripts\python.exe frontend/server.py
```

The frontend proxy runs at `http://127.0.0.1:5500` and proxies API requests to the backend at `http://127.0.0.1:8000`.

### Verify Frontend

```powershell
.venv\Scripts\python.exe -c "import httpx; print(httpx.get('http://127.0.0.1:5500/').status_code)"
```

Expected: `200`

## Step 4: Access the Application

Open your browser to: `http://127.0.0.1:5500`

Three sandboxes are available:
1. **RAG Knowledge Sandbox** — Upload documents and ask questions
2. **Resume Sandbox** — Upload and manage resume PDFs
3. **Job Application Sandbox** — Job analysis and email draft workflow

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AEGISCORE_DATA_DIR` | `./data` | Data directory for SQLite and uploads |
| `AEGISCORE_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama API endpoint |
| `AEGISCORE_CHAT_MODEL` | `phi3.5:3.8b` | Generation model |
| `AEGISCORE_EMBEDDING_MODEL` | `nomic-embed-text:latest` | Embedding model |

### Set Custom Data Directory

```powershell
$env:AEGISCORE_DATA_DIR = "C:\path\to\data"
```

## Running Tests

```powershell
.venv\Scripts\python.exe -m pytest backend/tests -v --strict-markers
```

Expected: All tests pass (currently 198 tests).

## Data Persistence

- SQLite database: `aegiscore.db` in `AEGISCORE_DATA_DIR`
- Uploaded files: `uploads/` subdirectory
- Data persists across server restarts

## Troubleshooting

See `TROUBLESHOOTING.md` for common issues.
