# AegisCore AI — Phase 4 Verification Plan

**Project:** C:\Users\shiva\OneDrive\Desktop\AegisCore-AI
**Branch:** checkpoint/phase4-verified-phase5-wip
**Latest commit:** 4b70a56 chore: checkpoint verified AegisCore AI implementation
**Verification date:** 2026-11-09
**Baseline:** 371 tests passing, pip check clean

## 1. Purpose

This document is the verification plan for Phase 4 — Multi-Document RAG System. It is a VERIFICATION-ONLY task. No new implementation will be created unless a genuine defect prevents verification.

## 2. Feature-to-File Mapping

| Feature | Source File(s) | Test File(s) |
|---------|---------------|--------------|
| Document upload & validation | `document_service.py` | `test_document_upload.py`, `test_part4_edge_security.py` |
| Text extraction (PDF/TXT/MD) | `extraction_service.py` | `test_extraction_service.py`, `test_extraction_integration.py` |
| Extraction persistence | `extraction_storage.py` | `test_extraction_integration.py` |
| Page-aware chunking | `chunking_service.py` | `test_chunking_service.py` |
| Chunk persistence | `chunk_storage.py` | `test_chunk_storage.py` |
| Ollama embeddings | `embedding_service.py`, `ollama_embedding.py` | `test_embedding_service.py` |
| Vector storage + cosine search | `vector_storage.py` | `test_vector_search.py` |
| BM25 sparse retrieval | `sparse_search.py` | `test_sparse_retrieval.py` |
| Hybrid RRF fusion | `sparse_search.py::hybrid_search` | `test_sparse_retrieval.py` |
| RAG QA with citations | `main.py:/ask` | `test_rag_qa.py`, `test_part4_citation_integrity.py` |
| Multi-document single answer | `main.py:/ask` | `test_part4_multi_document.py` |
| Citation integrity / abstention | `main.py:/ask`, `partial_support.py` | `test_part4_citation_integrity.py` |
| Persistence & restart recovery | SQLite + file storage | `test_part4_restart_recovery.py` |
| Document edge cases & security | `document_service.py` | `test_part4_edge_security.py` |

## 3. Acceptance Criteria to Verify

| # | Criterion | Required Evidence |
|---|-----------|-------------------|
| 1 | Full backend regression suite passes | `pytest backend/tests --strict-markers` = 0 failures |
| 2 | Cross-document single-answer test passes with both valid citations | `test_part4_multi_document.py` |
| 3 | Retrieval: dense, sparse, hybrid verified | `test_vector_search.py`, `test_sparse_retrieval.py` |
| 4 | Citation integrity & abstention tests pass | `test_part4_citation_integrity.py` |
| 5 | Restart persistence/recovery tests pass | `test_part4_restart_recovery.py` |
| 6 | Document edge cases & security checks pass | `test_part4_edge_security.py` |
| 7 | Live PDF-to-RAG citation verification passes | Live API + PDF upload → page citation |
| 8 | Dependency & whitespace checks pass | `pip check`, no whitespace errors |
| 9 | Evidence files accurately reflect execution | Verification scripts + logs |
| 10 | No unrelated user changes lost | Git status clean of unintended changes |

## 4. Gaps to Document (not fix without approval)

| Gap | Description | Impact |
|-----|-------------|--------|
| Cross-encoder reranking | Not implemented; hybrid RRF fusion used instead | Optional feature; document as limitation |
| Configurable retrieval weights | RRF uses fixed rrf_k=60 | Minor; document as limitation |
| No Docker/Kubernetes | Not required for local deployment | Document as limitation |

## 5. Verification Execution Order

1. Baseline test suite (confirm 371 passing)
2. Document upload/extraction/chunking/embedding pipeline
3. Retrieval pipeline (dense, sparse, hybrid)
4. Multi-document QA with citations
5. Citation integrity & abstention
6. Persistence & restart recovery
7. Document edge cases & security
8. Reranking & hybrid fusion documentation
9. Full regression + dependency checks
10. Evidence collection & report

## 6. Rules

- No mock data presented as live integration evidence
- No failing tests suppressed or weakened
- No API keys/secrets exposed
- Real API tests using actual FastAPI routes
- Isolated temp data directories for integration tests
- Timeouts and safe server cleanup
- Non-zero exit codes on failure
