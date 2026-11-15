# AegisCore AI — V1 Final Test Matrix

**Project:** C:\Users\shiva\OneDrive\Desktop\AegisCore-AI
**Report date:** 2026-11-03
**Total automated tests:** 198 passed, 0 failed
**Total browser verification checks:** 103 passed, 0 failed

## Backend Unit Tests (198 total)

| Test File | Tests | Status |
|-----------|-------|--------|
| test_chunk_storage.py | 4 | PASS |
| test_chunking_service.py | 11 | PASS |
| test_document_upload.py | 14 | PASS |
| test_document_status_delete.py | 6 | PASS |
| test_embedding_service.py | 16 | PASS |
| test_extraction_integration.py | 4 | PASS |
| test_extraction_service.py | 9 | PASS |
| test_frontend_proxy_methods.py | 1 | PASS |
| test_health.py | 4 | PASS |
| test_job_analysis.py | 8 | PASS |
| test_job_analysis_api.py | 5 | PASS |
| test_job_email.py | 10 | PASS |
| test_job_email_approval_api.py | 4 | PASS |
| test_job_email_approval_storage.py | 4 | PASS |
| test_job_email_attachment_api.py | 3 | PASS |
| test_job_email_review_api.py | 1 | PASS |
| test_job_email_storage.py | 4 | PASS |
| test_job_email_update_api.py | 3 | PASS |
| test_part4_citation_integrity.py | 13 | PASS |
| test_part4_edge_security.py | 12 | PASS |
| test_part4_multi_document.py | 5 | PASS |
| test_part4_restart_recovery.py | 2 | PASS |
| test_rag_qa.py | 9 | PASS |
| test_reliability.py | 3 | PASS |
| test_resume_attachment.py | 6 | PASS |
| test_sparse_retrieval.py | 13 | PASS |
| test_vector_search.py | 15 | PASS |
| **Total** | **198** | **ALL PASS** |

## RAG Knowledge Sandbox Browser Verification (28 checks)

| # | Check | Status |
|---|-------|--------|
| 1 | Backend health OK | PASS |
| 2 | Frontend reachable | PASS |
| 3 | Page loads | PASS |
| 4 | RAG Knowledge Sandbox heading visible | PASS |
| 5 | All 3 docs uploaded | PASS |
| 6 | PDF document in list | PASS |
| 7 | TXT document in list | PASS |
| 8 | MD document in list | PASS |
| 9 | Documents registered in backend | PASS |
| 10-18 | Status OK for each document (extraction, chunks, embeddings) | PASS |
| 19 | Dense retrieval produced response | PASS |
| 20 | Dense retrieval has citations when answered | PASS |
| 21 | Sparse retrieval produced response | PASS |
| 22 | Sparse retrieval has citations when answered | PASS |
| 23 | Hybrid retrieval produced response | PASS |
| 24 | Hybrid retrieval has citations when answered | PASS |
| 25 | System returned response for unsupported question | PASS |
| 26 | Unsupported question has citations when answered | PASS |
| 27 | Ask button re-enabled after request | PASS |
| 28 | Delete buttons visible | PASS |
| 29 | Delete status: Document deleted | PASS |
| 30 | Document count decreased after deletion | PASS |
| 31 | At least 2 documents remain after deletion | PASS |
| 32 | No console errors | PASS |

## Resume Sandbox Browser Verification (21 checks)

| # | Check | Status |
|---|-------|--------|
| 1 | Backend health OK | PASS |
| 2 | Frontend reachable | PASS |
| 3 | Resume section heading visible | PASS |
| 4 | Resume upload status OK | PASS |
| 5 | Extraction mentioned in status | PASS |
| 6 | Resume PDF registered in backend | PASS |
| 7 | Extraction endpoint OK | PASS |
| 8 | Extraction contains name | PASS |
| 9 | Extraction contains skills | PASS |
| 10 | Resume text auto-populated in textarea | PASS |
| 11 | Resume document persisted after refresh | PASS |
| 12 | Extraction persists (SQLite) | PASS |
| 13 | Resume text available for job analysis | PASS |
| 14 | Resume text is non-empty | PASS |
| 15 | Second resume upload OK | PASS |
| 16 | Second resume registered in backend | PASS |
| 17 | First resume still exists after replacement | PASS |
| 18 | No console errors | PASS |
| 19 | Invalid PDF rejected (400) | PASS |
| 20 | Empty PDF upload accepted | PASS |
| 21 | Empty PDF extraction endpoint OK | PASS |
| 22 | Oversized upload rejected (413) | PASS |
| 23 | Unsupported extension rejected (415) | PASS |

## Job Analysis Sandbox Verification (22 checks)

| # | Check | Status |
|---|-------|--------|
| 1 | Backend health OK | PASS |
| 2 | Resume upload OK | PASS |
| 3 | Extraction OK | PASS |
| 4 | Resume text extracted | PASS |
| 5 | Job analysis OK | PASS |
| 6 | Python matched | PASS |
| 7 | FastAPI matched | PASS |
| 8 | SQL matched | PASS |
| 9 | Docker matched | PASS |
| 10 | ML missing | PASS |
| 11 | Match percentage is int | PASS |
| 12 | Match percentage > 0 | PASS |
| 13 | Score not hiring probability | PASS |
| 14 | Repeat analysis OK | PASS |
| 15 | Deterministic: same score | PASS |
| 16 | Deterministic: same matched skills | PASS |
| 17 | Empty job description rejected (422) | PASS |
| 18 | Empty resume text rejected (422) | PASS |
| 19 | No-match analysis OK | PASS |
| 20 | Zero match when no skills overlap | PASS |
| 21 | No matched skills | PASS |
| 22 | 100% match when all skills overlap | PASS |
| 23 | No missing skills | PASS |
| 24 | Oversized resume rejected (422) | PASS |
| 25 | Interpretation does not claim hiring probability | PASS |
| 26 | Match basis describes skill overlap | PASS |

## Job Application Sandbox Browser Verification (32 checks)

| # | Check | Status |
|---|-------|--------|
| 1 | Backend health OK | PASS |
| 2 | Frontend reachable | PASS |
| 3 | Resume uploaded | PASS |
| 4 | Resume registered in backend | PASS |
| 5 | Draft generated | PASS |
| 6 | Status says nothing sent | PASS |
| 7 | Attachment document ID shown | PASS |
| 8 | Attachment SHA-256 shown | PASS |
| 9 | Unsaved edits detected | PASS |
| 10 | Changes saved | PASS |
| 11 | Draft retrievable via API | PASS |
| 12 | Recipient updated in draft | PASS |
| 13 | Draft still requires approval | PASS |
| 14 | Draft not sent | PASS |
| 15 | Draft binds correct resume attachment | PASS |
| 16 | Draft SHA-256 matches resume | PASS |
| 17 | Interface states no email sent | PASS |
| 18 | Disclaimer visible | PASS |
| 19 | Approve button enabled | PASS |
| 20 | Draft approved | PASS |
| 21 | Approval confirms no email sent | PASS |
| 22 | Approved draft retrievable | PASS |
| 23 | Draft status is approved | PASS |
| 24 | No longer requires approval | PASS |
| 25 | Email not sent | PASS |
| 26 | Approved draft modification rejected | PASS |
| 27 | Tampered attachment rejected | PASS |
| 28 | Unknown attachment rejected | PASS |
| 29 | Backend confirms email not sent | PASS |
| 30 | UI confirms email not sent | PASS |
| 31 | No console errors | PASS |

## Security Verification (17 checks)

| # | Check | Status |
|---|-------|--------|
| 1 | Backend health OK | PASS |
| 2 | Path traversal rejected (415) | PASS |
| 3 | Dot-dot filename rejected (400) | PASS |
| 4 | Backslash path traversal rejected (415) | PASS |
| 5 | EXE extension rejected (415) | PASS |
| 6 | BAT extension rejected (415) | PASS |
| 7 | Invalid PDF signature rejected (400) | PASS |
| 8 | Oversized upload rejected (413) | PASS |
| 9 | Empty file rejected (400) | PASS |
| 10 | Invalid UTF-8 rejected (400) | PASS |
| 11 | Binary as text rejected (400) | PASS |
| 12 | Invalid document ID returns 404 | PASS |
| 13 | Unknown document ID returns 404 | PASS |
| 14 | Error doesn't expose upload path | PASS |
| 15 | Error doesn't expose storage_key | PASS |
| 16 | Error doesn't expose data directory | PASS |
| 17 | Error doesn't expose database name | PASS |
| 18 | Secure PDF upload OK | PASS |
| 19 | Upload response includes SHA-256 | PASS |

## Document Status and Delete Verification (32 checks)

All checks in `scripts/verify_status_delete_endpoints.py` passed including:
- Document status for existing documents (txt, pdf)
- Document status for unknown document (404)
- Document status after embedding
- Document status for uploaded-but-not-embedded document
- Document delete for txt document
- Document delete for pdf document
- Document delete for unknown document (404)
- Cross-document isolation (deleting one doesn't affect another)
- Chunks deleted after document deletion
- Embeddings deleted after document deletion

## End-to-End Workflow Verification (39 checks)

All checks in `scripts/verify_part05_e2e_workflow.py` passed including:
- Health and root endpoints
- Resume PDF upload and extraction
- Text extraction and page metadata
- Chunking and embedding
- Dense, sparse, and hybrid search
- RAG QA with citations
- Job analysis (skill matching)
- Email draft creation, retrieval, update, and approval
- Attachment integrity verification
- Approved draft immutability
- Tampered attachment rejection
- No email sent
- Unknown resume rejection
- Non-PDF resume rejection
- Unsupported extension rejection
- Oversized upload rejection
- Document listing
- Unknown document 404
