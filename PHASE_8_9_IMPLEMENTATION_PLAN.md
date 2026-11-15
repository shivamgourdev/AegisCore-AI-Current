# AegisCore AI — Phase 8 & 9 Implementation Plan

**Project:** C:\Users\shiva\OneDrive\Desktop\AegisCore-AI
**Branch:** checkpoint/phase4-verified-phase5-wip
**Latest commit:** 4b70a56 chore: checkpoint verified AegisCore AI implementation
**Plan date:** 2026-11-09
**Baseline:** 371 tests passing, pip check clean

## Phase 8 — Advanced RAG & Evidence System

### Gap Analysis

| Feature | Existing Implementation | Gap | Action Required |
|---------|------------------------|-----|-----------------|
| Dense/sparse/hybrid retrieval | `sparse_search.py`, `vector_storage.py` | Exists | None |
| Citations with source_id, filename, page_number | `main.py:/ask` | Exists | None |
| Citation validation endpoint | Missing | **Missing** | Create `GET /citations/{citation_id}/validate` |
| Source preview endpoint | Missing | **Missing** | Create `GET /documents/{id}/preview` |
| Enhanced citation metadata (document_id, chunk_id) | `main.py` has document_id in sources | Partial | Add chunk_id to citation sources |

### Files to Modify
- `backend/app/aegiscore/main.py` - Add citation validation and source preview endpoints

### Files to Create
- `backend/tests/test_phase8_citation_validation.py` - Unit tests for citation validation
- `scripts/verify_part08_e2e_workflow.py` - E2E verification script

### Files Preserved (Untouched)
- All Phase 1-7 source files and test files

---

## Phase 9 — Persistent Resume Manager Sandbox

### Gap Analysis

| Feature | Existing Implementation | Gap | Action Required |
|---------|------------------------|-----|-----------------|
| Resume upload | `document_service.py` | Exists | Reuse |
| Resume text extraction | `extraction_service.py` | Exists | Reuse |
| Resume persistence | SQLite + file storage | Exists | Reuse |
| Resume document ID | `document_service.py` | Exists | Reuse |
| Resume preview | Missing | **Missing** | Create preview/download endpoint |
| Resume version history | Missing | **Missing** | Version tracking |
| Active version selection | Missing | **Missing** | Track active version |
| Resume Manager UI section | Missing | **Missing** | Create dedicated sandbox section |
| SHA-256 integrity on resume | `document_service.py` | Exists | Reuse |
| Duplicate upload detection | `document_service.py` | Exists | Reuse |

### Files to Create
- `backend/app/aegiscore/resume_manager.py` - Resume version management logic
- `backend/tests/test_resume_manager.py` - Unit tests for resume manager
- `scripts/verify_part09_resume_manager.py` - E2E verification

### Files to Modify
- `frontend/index.html` - Add Resume Manager sandbox section (separate from Job Application)

### Files Preserved (Untouched)
- All Phase 1-7 source files and test files

---

## 9. Security Rules for Phase 8 & 9

- No email delivery
- No OCR or image intelligence
- No paid APIs
- File type validation (PDF/TXT/MD for RAG, PDF only for resume)
- Path traversal prevention
- SHA-256 attachment integrity
- No real personal resume data in tests
- No secrets exposed in logs
