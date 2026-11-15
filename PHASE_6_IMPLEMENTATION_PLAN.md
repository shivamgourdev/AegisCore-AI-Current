# AegisCore AI — Phase 6: Unified Sandbox UI — Implementation Plan

**Project:** C:\Users\shiva\OneDrive\Desktop\AegisCore-AI
**Branch:** checkpoint/phase4-verified-phase5-wip
**Latest commit:** 4b70a56 chore: checkpoint verified AegisCore AI implementation
**Plan date:** 2026-11-09
**Baseline:** 371 tests passing, pip check clean

## 1. Phase Objective

Create a unified sandbox UI for AegisCore AI — a single, clean, professional interface that combines the existing RAG Knowledge Sandbox and Job Application Sandbox into one cohesive user experience with two tabbed workspaces.

## 2. Frontend Audit — Existing State

### Current frontend files:

| File | Purpose | Status |
|------|---------|--------|
| `frontend/index.html` | Single HTML file with inline CSS/JS containing both sandboxes | Exists |
| `frontend/server.py` | API proxy on port 5500, routes `/api/` to backend:8000 | Exists |

### Feature-to-file mapping:

| Feature | Existing Implementation | Location | Status |
|---------|------------------------|----------|--------|
| Document upload (PDF/TXT/MD) | `/documents/upload` | backend `main.py` line 90 | Verified |
| RAG search (dense/sparse/hybrid) | `/search` | backend `main.py` line 195 | Verified |
| RAG QA with citations | `/ask` | backend `main.py` line 475 | Verified |
| Document list | `/documents` | backend `main.py` line 287 | Verified |
| Document deletion | `DELETE /documents/{id}` | backend `main.py` line 343 | Verified |
| Document status | `GET /documents/{id}/status` | backend `main.py` line 304 | Verified |
| Document extraction | `GET /documents/{id}/extraction` | backend `main.py` line 292 | Verified |
| Document chunks | `GET /documents/{id}/chunks` | backend `main.py` line 142 | Verified |
| Job skill analysis | `/jobs/analyze` | backend `main.py` line 939 | Verified |
| Email draft creation | `POST /jobs/email-draft` | backend `main.py` line 1112 | Verified |
| Draft retrieval | `GET /jobs/email-drafts/{id}` | backend `main.py` line 990 | Verified |
| Draft update | `PUT /jobs/email-drafts/{id}` | backend `main.py` line 1005 | Verified |
| Draft approval | `POST /jobs/email-drafts/{id}/approve` | backend `main.py` line 1061 | Verified |
| Frontend proxy | `frontend/server.py` routes `/api/` → `:8000` | Exists | Verified |

### Frontend proxy coverage:

| Frontend route | Backend route | Covered? |
|----------------|---------------|----------|
| `/api/documents/upload` | `/documents/upload` | Yes |
| `/api/documents/{id}/extraction` | `/documents/{id}/extraction` | Yes |
| `/api/documents/{id}/chunks` | `/documents/{id}/chunks` | Yes |
| `/api/documents/{id}/embed` | `/documents/{id}/embed` | Yes |
| `/api/documents/{id}/status` | `/documents/{id}/status` | Yes |
| `/api/documents` | `/documents` | Yes |
| `/api/documents/{id}` (DELETE) | `/documents/{id}` | Yes |
| `/ask` | `/ask` | Yes |
| `/api/jobs/analyze` | `/jobs/analyze` | Yes |
| `/api/jobs/email-draft` | `/jobs/email-draft` | Yes |
| `/api/jobs/email-drafts/{id}` | `/jobs/email-drafts/{id}` | Yes |
| `/api/jobs/email-drafts/{id}` (PUT) | `/jobs/email-drafts/{id}` | Yes |
| `/api/jobs/email-drafts/{id}/approve` | `/jobs/email-drafts/{id}/approve` | Yes |

**All existing API routes are already covered by the frontend proxy.**

### Current UI issues to address in Phase 6:

1. **Two separate sandboxes stacked vertically** — No clear separation or navigation between them
2. **No unified workspace concept** — Users must scroll between sections
3. **No tabbed navigation** — All content visible at once, can be overwhelming
4. **No global state** — Resume uploaded in one section not easily accessible in another
5. **No consistent error/loading states** across sections

---

## 3. Implementation Plan

### Part 1 — Frontend Audit (Complete)

See table above. All backend API routes are already proxied by `frontend/server.py`. No new backend endpoints are needed.

### Part 2 — Unified Sandbox Interface

**Design:**
- Single-page application with two tabbed workspaces
- **Workspace A: Knowledge Assistant** — Document upload, list, search, Q&A with citations
- **Workspace B: Job Application Assistant** — Resume upload, job analysis, email draft, review & approve
- Shared state: uploaded resume document carries across workspaces
- Consistent loading/error states
- Consistent styling

**Files to modify:**
- `frontend/index.html` — Rewrite with unified tabbed UI
- `frontend/server.py` — No changes needed (all routes already proxied)

**No new backend endpoints needed.**

---

## 4. Security Rules

- No email sending (existing rule preserved)
- No OCR/image intelligence
- No paid APIs
- File validation at backend (already implemented)
- Path traversal prevention (already in backend)
- No secrets exposed in frontend

---

## 5. Tests

- Existing 371 tests must all still pass
- No new backend tests needed (no backend changes)
- Manual browser verification of unified UI

---

## 6. Deliverables

- `PHASE_6_IMPLEMENTATION_PLAN.md` (this file)
- Modified `frontend/index.html` — Unified sandbox UI
- `PHASE_6_IMPLEMENTATION_REPORT.md` — Post-implementation report
- `PHASE_6_TEST_MATRIX.md` — Test coverage
- `PHASE_6_SECURITY_REPORT.md` — Security assessment
- `PHASE_6_INDEPENDENT_AUDIT_REPORT.md` — Independent audit

---

## 7. Rules

- Do not modify backend source code
- Do not modify existing tests
- Do not commit or push
- Preserve all existing functionality
- Back up `frontend/index.html` before modification
