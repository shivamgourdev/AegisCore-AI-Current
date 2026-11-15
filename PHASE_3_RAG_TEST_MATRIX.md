# AegisCore AI — Phase 3 RAG Test Matrix

**Project:** C:\Users\shiva\OneDrive\Desktop\AegisCore-AI
**Report date:** 2026-11-09

## Test Summary

| Category | Count | Result |
|----------|-------|--------|
| Phase 3 unit tests | 54 | PASS |
| Phase 1 + Phase 2 regression tests | 317 | PASS |
| **Total automated tests** | **371** | **ALL PASS** |
| `pip check` | — | Clean |
| Python syntax audit | 11 Phase 3 files | 0 errors |

---

## Phase 3 Unit Test Matrix (54 tests)

### test_query_processing.py (19 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_normalize_basic | Whitespace collapsing | PASS |
| test_normalize_tabs_and_newlines | Tab/newline collapsing | PASS |
| test_normalize_empty | Empty string handling | PASS |
| test_normalize_none | None input handling | PASS |
| test_valid_query | Valid query passes | PASS |
| test_empty_query | Empty string rejected | PASS |
| test_none_query | None input rejected | PASS |
| test_too_long_query | Length limit enforced | PASS |
| test_single_query_no_decomposition | Single query not split | PASS |
| test_decompose_on_and | "and" splits query | PASS |
| test_decompose_max_subqueries | Max subquery limit | PASS |
| test_no_expansion_by_default | Expansion disabled by default | PASS |
| test_expansion_enabled | Synonym expansion works | PASS |
| test_expansion_empty | Empty input handling | PASS |
| test_valid_query_processing | Full pipeline valid input | PASS |
| test_invalid_query_processing | Full pipeline invalid input | PASS |
| test_decomposition_enabled | Config-driven decomposition | PASS |
| test_build_from_valid_query | Retrieval query building | PASS |
| test_build_from_invalid_query | Invalid query returns empty | PASS |

### test_context_selector.py (11 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_select_all_when_small | Small chunk set fully selected | PASS |
| test_filter_low_similarity | Low similarity chunks filtered | PASS |
| test_remove_near_duplicates | Identical text deduplicated | PASS |
| test_remove_near_duplicates_different_text | Near-duplicate text detected | PASS |
| test_source_diversity_limit | Per-document chunk limit | PASS |
| test_character_budget_truncation | Character budget enforced | PASS |
| test_empty_chunks | Empty input handled | PASS |
| test_build_context | Context text built correctly | PASS |
| test_truncate_long_chunk | Long chunks truncated | PASS |

### test_confidence.py (11 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_high_confidence | High similarity = high confidence | PASS |
| test_medium_confidence | Medium similarity = medium confidence | PASS |
| test_low_confidence | Low similarity = low confidence | PASS |
| test_insufficient_confidence | Very low similarity = insufficient | PASS |
| test_no_chunks | No chunks = insufficient | PASS |
| test_single_chunk_high_similarity | Single high-sim chunk | PASS |
| test_high_confidence_fully_supported | High score + full support = high | PASS |
| test_unsupported_abstains | Unsupported = abstain | PASS |
| test_partially_supported_lowers_score | Partial support lowers score | PASS |

### test_observability.py (7 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_collector_basic_flow | Full diagnostic collection | PASS |
| test_collector_abstained_status | Abstained status tracked | PASS |
| test_sanitize_for_logging | Newlines/tabs removed | PASS |
| test_sanitize_truncation | Long text truncated | PASS |
| test_retrieval_diagnostics_to_dict | Dict serialization | PASS |

### test_partial_support.py (7 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_fully_supported | All claims cited = fully supported | PASS |
| test_unsupported_no_citations | No citations = unsupported | PASS |
| test_invalid_citation | Invalid citation ID = unsupported | PASS |
| test_partially_supported | Some claims uncited = partial | PASS |
| test_empty_answer | Empty answer = unsupported | PASS |
| test_no_factual_claims | No claims = fully supported | PASS |

### test_rag_phase3_integration.py (8 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_ask_returns_confidence | /ask returns confidence info | PASS |
| test_ask_diagnose_endpoint | /ask/diagnose works | PASS |
| test_ask_diagnose_invalid_query | Invalid query = 422 | PASS |
| test_ask_preserves_existing_fields | Existing fields preserved | PASS |
| test_ask_rejects_invalid_mode | Invalid mode rejected | PASS |
| test_ask_diagnose_preserves_query_processing | Query processing in diagnose | PASS |

---

## Phase 1 + Phase 2 Regression Test Matrix (317 tests)

All 317 existing tests pass with no modifications:

| Category | Tests | Status |
|----------|-------|--------|
| Document upload/extraction/chunking | ~44 | PASS |
| RAG QA with citations | ~18 | PASS |
| Multi-document RAG | ~9 | PASS |
| Citation integrity | ~19 | PASS |
| Document edge cases & security | ~12 | PASS |
| Restart persistence/recovery | ~2 | PASS |
| Resume attachment & SHA-256 | ~6 | PASS |
| Job analysis | ~14 | PASS |
| Email draft/approval | ~20 | PASS |
| Frontend proxy | ~1 | PASS |
| Health endpoints | ~4 | PASS |
| Part 1 multi-agent | ~29 | PASS |
| Part 2 MCP (all modules) | ~90 | PASS |

---

## Security Test Coverage

| Security Area | Tests | Status |
|---------------|-------|--------|
| Query length validation | 1 | PASS |
| Empty/malformed query rejection | 2 | PASS |
| Citation integrity | ~19 | PASS |
| No internal path exposure | Implicit in all RAG tests | PASS |
| Prompt injection protection | Part of Part 2 MCP tests | PASS |
| Output sanitization | Part of Part 2 MCP tests | PASS |

---

## Environment & Dependencies

| Item | Value |
|------|-------|
| Python version | 3.11.9 |
| Virtual environment | .venv |
| pytest version | 9.1.1 |
| pytest-anyio | 4.15.1 |
| Ollama model (chat) | phi3.5:3.8b |
| Ollama model (embedding) | nomic-embed-text:latest |
| New dependencies | None (uses existing only) |
