# AegisCore AI — API Documentation

**Base URL:** `http://127.0.0.1:8000`
**OpenAPI Schema:** `http://127.0.0.1:8000/openapi.json`

## Document Endpoints

### Upload Document
```
POST /documents/upload
Content-Type: multipart/form-data
Body: file=<file>
```
Upload a PDF, TXT, or MD file. Returns document metadata including document_id, filename, sha256, and extraction status.

### List Documents
```
GET /documents
```
Returns all registered documents with metadata.

### Get Document Status
```
GET /documents/{document_id}/status
```
Returns per-document status: extraction status, page count, chunk count, embedding count, embedding model.

### Get Document Extraction
```
GET /documents/{document_id}/extraction
```
Returns extracted text and page-level source metadata.

### Get Document Chunks
```
GET /documents/{document_id}/chunks
```
Returns text chunks with source metadata (page number, chunk index).

### Get Document Embeddings
```
GET /documents/{document_id}/embeddings
```
Returns stored embeddings for the document.

### Embed Document
```
POST /documents/{document_id}/embed
```
Generates and persists embeddings for the document's chunks.

### Delete Document
```
DELETE /documents/{document_id}
```
Deletes the document, its chunks, embeddings, extraction data, and stored file.

## Search Endpoints

### Search Documents
```
POST /search
Content-Type: application/json
Body: {"query": "...", "top_k": 5, "mode": "dense|sparse|hybrid"}
```
Search chunks using dense (vector), sparse (BM25), or hybrid (RRF fusion) retrieval.

## RAG Endpoints

### Ask Question
```
POST /ask
Content-Type: application/json
Body: {"query": "...", "top_k": 5, "min_similarity": 0.45}
```
Ask a question across uploaded documents. Returns answer with citations or abstention status.

## Job Analysis Endpoints

### Analyze Skills
```
POST /jobs/analyze
Content-Type: application/json
Body: {"resume_text": "...", "job_description": "..."}
```
Returns matched skills, missing skills, match percentage, and interpretation.

## Email Draft Endpoints

### Create Draft
```
POST /jobs/email-draft
Content-Type: application/json
Body: {candidate_name, recipient_email, job_title, company_name, resume_summary, resume_document_id}
```
Creates and saves an email draft bound to a verified PDF resume attachment.

### Get Draft
```
GET /jobs/email-drafts/{draft_id}
```
Returns the draft with current status and content.

### Update Draft
```
PUT /jobs/email-drafts/{draft_id}
Content-Type: application/json
Body: {recipient_email, subject, body}
```
Updates a pending draft. Approved drafts cannot be modified.

### Approve Draft
```
POST /jobs/email-drafts/{draft_id}/approve
Content-Type: application/json
Body: {recipient_email, subject, body, attachment_document_id, attachment_sha256, confirm: true}
```
Explicitly approves the draft. No email is sent. Approved drafts are immutable.

## Response Format

All API responses are JSON. Error responses include a `detail` field with a human-readable message. HTTP status codes follow REST conventions (200 success, 400 bad request, 404 not found, 415 unsupported media type, 413 too large, 409 conflict).
