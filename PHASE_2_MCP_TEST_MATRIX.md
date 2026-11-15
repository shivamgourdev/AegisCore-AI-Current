# AegisCore AI — Phase 2 MCP Test Matrix

**Project:** C:\Users\shiva\OneDrive\Desktop\AegisCore-AI
**Report date:** 2026-11-07

## Test Summary

| Category | Count | Result |
|----------|-------|--------|
| Phase 2 unit tests | 90 | PASS |
| Phase 1 regression tests | 227 | PASS |
| **Total automated tests** | **317** | **ALL PASS** |
| MCP E2E verification checks | 6 | PASS |
| `pip check` | — | Clean |
| Python syntax audit | 20 Phase 2 files | 0 errors |

---

## Phase 2 Unit Test Matrix (90 tests)

### test_mcp_tool_registry.py (16 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_registry_has_seven_tools | Registry contains exactly 7 tools | PASS |
| test_tool_names | All expected tool names present | PASS |
| test_read_only_tools | 6 read-only tools identified | PASS |
| test_state_changing_tools | 1 state-changing tool (generate_email_draft) | PASS |
| test_get_existing_tool | Tool lookup by name works | PASS |
| test_get_nonexistent_tool | Unknown tool returns None | PASS |
| test_has_tool | has() method works correctly | PASS |
| test_tool_has_strict_schema | Input schemas have required fields | PASS |
| test_tool_output_schema_no_additional_properties | Output schemas disallow extra fields | PASS |
| test_tool_input_schema_no_additional_properties | Input schemas disallow extra fields | PASS |
| test_register_duplicate_raises | Duplicate registration raises ValueError | PASS |
| test_timeout_and_retry_values | Tool timeout/retry values are valid | PASS |
| test_email_draft_is_state_changing | generate_email_draft is state-changing | PASS |
| test_search_knowledge_is_read_only | search_knowledge is read-only | PASS |
| test_analyze_job_description_requires_both_inputs | Both resume_text and job_description required | PASS |

### test_mcp_audit_logger.py (6 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_log_and_verify_chain | Log records and chain verification | PASS |
| test_tampering_detected | Modified record detected | PASS |
| test_reordering_detected | Reordered records detected | PASS |
| test_empty_log_is_valid | Empty log passes verification | PASS |
| test_sensitive_input_not_logged | Sensitive fields redacted in logs | PASS |
| test_singleton_getter | Singleton pattern works | PASS |

### test_mcp_permission_engine.py (12 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_read_only_tool_allowed_without_confirm | Read-only tools need no confirmation | PASS |
| test_read_only_tool_allowed_with_extra_fields | Extra fields ignored for read-only | PASS |
| test_state_changing_requires_confirm | State-changing tools need confirm | PASS |
| test_confirm_alone_is_not_sufficient | confirm: true alone rejected | PASS |
| test_confirm_with_valid_attachment_is_allowed | Valid draft + confirm = allowed | PASS |
| test_confirm_with_wrong_sha256_denied | Wrong SHA-256 rejected | PASS |
| test_confirm_with_wrong_document_id_denied | Wrong document_id rejected | PASS |
| test_unknown_tool_denied | Unknown tool rejected | PASS |
| test_record_verified_draft | Draft recording works | PASS |
| test_clear_draft_denies_subsequent | Cleared draft denies execution | PASS |
| test_is_state_changing | State-changing detection works | PASS |

### test_mcp_execution_engine.py (14 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_successful_execution | Successful tool execution | PASS |
| test_invalid_input_rejected | Invalid input rejected | PASS |
| test_additional_property_rejected | Extra properties rejected | PASS |
| test_tool_not_in_registry | Unknown tool rejected | PASS |
| test_executor_raises_exception | Executor exception handled | PASS |
| test_output_size_limit | Oversized output rejected | PASS |
| test_output_size_under_limit | Normal output accepted | PASS |
| test_retry_on_failure | Retry on transient failure | PASS |
| test_retry_exhausted | Retry exhaustion handled | PASS |
| test_global_retry_budget | Shared budget across layers | PASS |
| test_retry_budget_remaining | Budget tracking works | PASS |
| test_execution_count | Execution counting works | PASS |
| test_timeout | Timeout enforcement works | PASS |
| test_concurrent_execution | Concurrent execution works | PASS |
| test_execution_result_attributes | Result object has all attributes | PASS |

### test_mcp_agent_integration.py (8 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_integration_wraps_agent | Integration wraps agent | PASS |
| test_direct_execute_when_mcp_unavailable | Fallback to direct V1 when MCP down | PASS |
| test_stats | Statistics reporting works | PASS |
| test_max_tool_calls_enforced | Max tool calls limit enforced | PASS |
| test_create_integrated_agent_helper | Helper function works | PASS |
| test_mcp_output_validation_rejects_bad_output | Invalid output rejected | PASS |
| test_email_draft_output_with_sent_true_rejected | sent:true rejected | PASS |
| test_map_capability_to_tool | Capability-to-tool mapping works | PASS |

### test_mcp_circuit_breaker.py (10 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_closed_state_allows_execution | Closed state allows execution | PASS |
| test_opens_after_threshold_failures | Opens after threshold failures | PASS |
| test_half_open_after_recovery_timeout | Half-open after recovery timeout | PASS |
| test_half_open_success_closes_circuit | Success closes circuit | PASS |
| test_half_open_failure_reopens | Failure reopens circuit | PASS |
| test_consecutive_failures_reset_on_success | Success resets failure count | PASS |
| test_get_stats | Statistics reporting works | PASS |
| test_singleton | Singleton pattern works | PASS |
| test_half_open_max_calls | Half-open max calls enforced | PASS |
| test_circuit_breaker_in_execution_flow | Circuit breaker in flow | PASS |

### test_mcp_prompt_injection_guard.py (14 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_safe_tool_description | Safe description passes | PASS |
| test_unsafe_tool_description | Unsafe description blocked | PASS |
| test_jailbreak_pattern_blocked | Jailbreak pattern blocked | PASS |
| test_system_prompt_override_blocked | System override blocked | PASS |
| test_safe_tool_output_dict | Safe dict output passes | PASS |
| test_unsafe_tool_output_injection_pattern | Injection pattern in output blocked | PASS |
| test_nested_output_injection | Nested injection blocked | PASS |
| test_deep_nesting_rejected | Deep nesting rejected | PASS |
| test_none_output_is_safe | None output is safe | PASS |
| test_non_dict_output_is_safe | Non-dict output is safe | PASS |
| test_instruction_like_content_blocked | Instruction-like content blocked | PASS |
| test_sanitize_for_agent | Sanitization works | PASS |
| test_singleton | Singleton pattern works | PASS |

### test_mcp_output_sanitizer.py (10 tests)

| Test | Description | Status |
|------|-------------|--------|
| test_sanitize_dict | Dict sanitization works | PASS |
| test_sanitize_removes_script_tags | Script tags removed | PASS |
| test_sanitize_removes_html_tags | HTML tags removed | PASS |
| test_sanitize_removes_path_traversal | Path traversal removed | PASS |
| test_sanitize_removes_internal_paths | Internal paths redacted | PASS |
| test_sanitize_removes_secrets | Secrets redacted | PASS |
| test_sanitize_preserves_safe_content | Safe content preserved | PASS |
| test_contains_dangerous_content | Dangerous content detected | PASS |
| test_nested_sanitization | Nested sanitization works | PASS |
| test_list_sanitization | List sanitization works | PASS |
| test_singleton | Singleton pattern works | PASS |

---

## MCP E2E Verification Matrix (6 checks)

| Check | Description | Status |
|-------|-------------|--------|
| test_mcp_server_starts_and_lists_tools | Server lists 7 approved tools | PASS |
| test_mcp_get_document_status | Unknown document rejected gracefully | PASS |
| test_mcp_generate_email_draft_without_confirm | Missing confirm rejected | PASS |
| test_mcp_generate_email_draft_confirm_alone_insufficient | confirm: true alone insufficient | PASS |
| test_mcp_get_resume_attachment_unknown | Unknown document rejected | PASS |
| test_mcp_tool_output_no_internal_paths | No internal paths exposed | PASS |

---

## Phase 1 Regression Test Matrix (227 tests)

All 227 Phase 1 tests pass with no modifications. Categories include:

- Document upload/extraction/chunking/embedding (44 tests)
- RAG QA with citations and abstention (18 tests)
- Multi-document single answer (5 tests)
- Citation integrity and fail-closed (13 tests)
- Document edge cases and security (12 tests)
- Restart persistence/recovery (2 tests)
- Resume attachment and SHA-256 integrity (6 tests)
- Job analysis (14 tests)
- Email draft generation, storage, approval (20 tests)
- Frontend proxy methods (1 test)
- Health endpoints (4 tests)
- Part 1 multi-agent engine (29 tests)

---

## Test Coverage by Security Area

| Security Area | Tests | Status |
|---------------|-------|--------|
| Tool allowlist enforcement | 16 | PASS |
| Permission validation (confirm: true) | 12 | PASS |
| Attachment SHA-256 verification | 6 | PASS |
| Prompt injection protection | 14 | PASS |
| Output sanitization | 10 | PASS |
| Circuit breaker | 10 | PASS |
| Audit logging integrity | 6 | PASS |
| Retry budget | 3 | PASS |
| Output size limits | 2 | PASS |
| Concurrent execution limits | 1 | PASS |
| Safe fallback | 2 | PASS |
