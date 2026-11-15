# AegisCore AI — Phase 10 Implementation Plan

**Project:** C:\Users\shiva\OneDrive\Desktop\AegisCore-AI
**Branch:** checkpoint/phase4-verified-phase5-wip
**Latest commit:** 4b70a56 chore: checkpoint verified AegisCore AI implementation
**Plan date:** 2026-11-12
**Baseline:** 378 tests passing, pip check clean

## 1. Phase Objective

Implement AI Hiring & Gmail Automation workflow:
- Hiring message text input (manual paste from WhatsApp, Telegram, LinkedIn, etc.)
- Hiring message image input (OCR for hiring posters, screenshots)
- Structured job information extraction
- Resume Manager integration (retrieve active resume)
- Email draft generation (no sending)
- Explicit user approval workflow

## 2. Architecture Design

### Components

| Component | File | Purpose |
|-----------|--------|---------|
| Hiring message upload | `backend/app/aegiscore/hiring.py` | Accept text or image input |
| OCR processing | `backend/app/aegiscore/ocr_service.py` | Extract text from hiring images |
| Job information extraction | `backend/app/aegiscore/job_analysis.py` | Reuse existing skill matching |
| Resume integration | `backend/app/aegiscore/resume_agent.py` | Get active resume |
| Email draft generation | `backend/app/aegiscore/job_email.py` | Reuse existing |
| Email draft storage | `backend/app/aegiscore/job_email_storage.py` | Reuse existing |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/jobs/hiring/upload` | POST | Upload hiring image (OCR) |
| `/jobs/hiring/text` | POST | Submit hiring message text |
| `/jobs/analyze-hiring` | POST | Structured job info extraction |
| `/jobs/hiring/draft` | POST | Generate email draft bound to resume |

### Security Rules

- No email delivery (sending is disabled)
- File validation for image uploads
- File size limits (10 MB max)
- Path traversal prevention
- OCR only for hiring inputs
- No paid APIs

---

## 3. Implementation Details

### hiring.py - Hiring Message Processing

```python
@app.post("/jobs/hiring/upload")
async def upload_hiring_image(...):
    # Validate image file
    # Run OCR
    # Return extracted text

@app.post("/jobs/hiring/text")
async def submit_hiring_text(...):
    # Accept text input
    # Return structured job info
```

### job_email.py (reuse existing)
- `generate_job_email()` already exists
- Returns draft with `sent: False`

### job_email_storage.py (reuse existing)
- `create_draft()` already exists
- `approve_draft()` already exists with SHA-256 verification

---

## 4. Security Rules

- No email delivery
- File type validation for images
- File size limits
- Path traversal prevention
- SHA-256 integrity
- No paid OCR services

---

## 5. Files Created

| File | Purpose |
|------|---------|
| `backend/app/aegiscore/hiring.py` | Hiring message input and processing |
| `backend/app/aegiscore/ocr_service.py` | OCR for hiring images |
| `backend/tests/test_phase10_hiring.py` | Phase 10 unit tests |

### Files Modified

| File | Change |
|------|--------|
| `backend/app/aegiscore/main.py` | Added hiring endpoints |

---

## 6. Tests to Create

| Test File | Tests |
|-----------|-------|
| `test_phase10_hiring.py` | Hiring upload, extraction, draft generation |

---

## 7. Exit Criteria

- All 378+ existing tests still pass
- New Phase 10 tests pass
- pip check clean
- No email sending implemented
- All API endpoints return proper responses
