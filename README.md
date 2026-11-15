# AegisCore AI

A production-oriented AI platform for multi-document question answering with evidence-backed citations and user-approved job application email workflows.

## Project Status

**V1 Release Candidate** — All three sandboxes implemented and verified:
- RAG Knowledge Sandbox: Multi-document upload, extraction, chunking, embedding, dense/sparse/hybrid retrieval, grounded Q&A with citations
- Resume Sandbox: PDF resume upload, text extraction, persistence, reuse in job analysis
- Job Application Sandbox: Job skill analysis, email draft generation, explicit approval workflow (no email sent)

## Quick Start

### Prerequisites
- Windows 11
- Python 3.11.9
- Virtual environment: `.venv`
- Ollama running locally with models: `phi3.5:3.8b` and `nomic-embed-text:latest`

### Start the Backend (port 8000)
```powershell
.venv\Scripts\python.exe -m uvicorn aegiscore.main:app --host 127.0.0.1 --port 8000
```
Run from `backend/app/` directory. Set `AEGISCORE_DATA_DIR` environment variable for custom data path.

### Start the Frontend Proxy (port 5500)
```powershell
.venv\Scripts\python.exe frontend/server.py
```
Run from project root. Access at `http://127.0.0.1:5500`.

### Run Tests
```powershell
.venv\Scripts\python.exe -m pytest backend/tests -v --strict-markers
```

## Architecture

Three integrated sandboxes share a common document storage layer:

| Sandbox | Purpose | Key Features |
|---------|---------|-------------|
| RAG Knowledge | Multi-document Q&A | Upload PDF/TXT/MD, dense/sparse/hybrid retrieval, citations, abstention |
| Resume | Resume management | PDF upload, extraction, persistence, SHA-256 integrity |
| Job Application | Job applications | Skill analysis, email drafts, explicit approval, attachment integrity |

## Data Storage

- SQLite database: `aegiscore.db` under `AEGISCORE_DATA_DIR` (default: `./data`)
- Uploaded files: `uploads/` subdirectory under data dir
- All data persists across server restarts

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AEGISCORE_DATA_DIR` | `./data` | Data directory path |
| `AEGISCORE_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama API endpoint |
| `AEGISCORE_CHAT_MODEL` | `phi3.5:3.8b` | Generation model |
| `AEGISCORE_EMBEDDING_MODEL` | `nomic-embed-text:latest` | Embedding model |

## Security

- File type validation (PDF, TXT, MD only)
- PDF signature validation
- File size limit (10 MB)
- Path traversal prevention
- SHA-256 attachment integrity verification
- Explicit user approval (no email sent without approval)
- No storage paths exposed in API responses

## Limitations

- No OCR for scanned/image-only PDFs
- No cross-encoder reranking (hybrid RRF fusion used instead)
- No Docker/Kubernetes configuration
- No actual email delivery
- No real email sending (approval is workflow state only)
