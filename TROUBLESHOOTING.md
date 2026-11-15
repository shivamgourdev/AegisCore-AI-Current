# AegisCore AI — Troubleshooting

## Backend Won't Start

**Symptom:** `uvicorn` command fails or port 8000 is already in use.

**Solutions:**
1. Make sure the virtual environment is activated: `.venv\Scripts\Activate.ps1`
2. Run from the `backend/app/` directory: `cd backend/app`
3. Check if port 8000 is free: `netstat -ano | findstr :8000`
4. Kill any process on port 8000: `taskkill /F /PID <pid>`

## Frontend Won't Load

**Symptom:** Browser shows error or blank page at `http://127.0.0.1:5500`.

**Solutions:**
1. Make sure the backend is running on port 8000 first
2. Start the frontend proxy: `.venv\Scripts\python.exe frontend/server.py`
3. Check if port 5500 is free
4. Verify the backend health: `http://127.0.0.1:8000/health`

## Ollama Connection Errors

**Symptom:** Embedding or generation fails with 503 or timeout.

**Solutions:**
1. Verify Ollama is running: `ollama list`
2. Pull required models: `ollama pull phi3.5:3.8b` and `ollama pull nomic-embed-text:latest`
3. Check Ollama API: `http://127.0.0.1:11434/api/tags`
4. Set `AEGISCORE_OLLAMA_URL` if Ollama is on a different host

## Document Upload Fails

**Symptom:** Upload returns 400, 413, or 415.

**Solutions:**
1. 400: Invalid filename, empty file, bad PDF signature, or invalid UTF-8
2. 413: File exceeds 10 MB size limit
3. 415: Unsupported file extension (only PDF, TXT, MD allowed)

## RAG Q&A Returns No Answer

**Symptom:** The system abstains instead of answering.

**Solutions:**
1. Make sure documents are uploaded and embedded
2. Check document status via `GET /documents/{id}/status`
3. Try a different retrieval mode (dense/sparse/hybrid)
4. Lower the `min_similarity` threshold
5. The question may genuinely not be answerable from uploaded documents

## Email Draft Approval Fails

**Symptom:** Approval returns 409 conflict.

**Solutions:**
1. Make sure `confirm: true` is included in the approval payload
2. Verify recipient, subject, and body match the saved draft exactly
3. Verify attachment document ID and SHA-256 match the stored resume
4. Approved drafts cannot be modified — create a new draft instead

## Data Not Persisting After Restart

**Symptom:** Documents missing after backend restart.

**Solutions:**
1. Verify `AEGISCORE_DATA_DIR` points to the same directory
2. Check that SQLite database `aegiscore.db` exists in the data directory
3. Check that uploaded files exist in `uploads/` subdirectory

## No Console Errors in Browser

**Symptom:** Frontend works but you want to verify no JavaScript errors.

**Solutions:**
1. Open browser Developer Tools (F12)
2. Check the Console tab for errors
3. All three sandboxes should have zero console errors
