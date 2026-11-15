# AegisCore AI — Phase 2 MCP Security Report

**Project:** C:\Users\shiva\OneDrive\Desktop\AegisCore-AI
**Report date:** 2026-11-07

## Security Assessment Summary

| Area | Status | Tests | Notes |
|------|--------|-------|-------|
| Tool allowlist enforcement | VERIFIED | 16 | Only 7 approved tools; no dynamic loading |
| Permission validation | VERIFIED | 12 | confirm: true necessary but NOT sufficient |
| Attachment SHA-256 integrity | VERIFIED | 6 | Hash verified before returning metadata |
| Prompt injection protection | VERIFIED | 14 | Structural validation, not keyword-only |
| Output sanitization | VERIFIED | 10 | Script tags, HTML, path traversal, secrets removed |
| Circuit breaker | VERIFIED | 10 | Opens after 5 failures; half-open recovery |
| Audit logging integrity | VERIFIED | 6 | Tamper-evident hash chain |
| Retry budget | VERIFIED | 3 | Shared across client, engine, agent layers |
| Output size limits | VERIFIED | 2 | 1 MB default per tool |
| Concurrent execution limits | VERIFIED | 1 | Maximum 5 concurrent executions |
| Safe fallback | VERIFIED | 2 | Fallback preserves same security policies |

---

## 1. Security Controls Implemented

### 1.1 Tool Allowlist (Fixed, No Dynamic Loading)

- Exactly 7 tools registered: `search_knowledge`, `get_document_status`, `list_documents`,
  `analyze_resume`, `analyze_job_description`, `generate_email_draft`, `get_resume_attachment`
- No dynamic tool loading — tools registered once at module load
- Unknown tools rejected with `denied` permission decision

### 1.2 Permission Engine

**Read-only tools** (`search_knowledge`, `get_document_status`, `list_documents`,
`analyze_resume`, `analyze_job_description`, `get_resume_attachment`):
- Execute without `confirm` parameter
- No state-changing side effects

**State-changing tools** (`generate_email_draft`):
- Require `confirm: true` AND valid draft/attachment verification
- `confirm: true` alone is NOT sufficient — draft must exist in storage,
  attachment document_id and SHA-256 must match stored draft
- Draft tracking mirrors V1 draft storage state

### 1.3 Attachment Security

- `get_resume_attachment` verifies SHA-256 hash of stored file against database record
- Metadata excludes internal storage paths (`storage_key` never exposed)
- Storage path used internally only for reading file bytes
- Path traversal prevention via `document_service.get_resume_attachment`

### 1.4 Prompt Injection Protection

- Tool descriptions are static strings (not LLM-generated)
- Tool outputs treated as untrusted data
- Structural validation detects injection patterns (not keyword-only scanning)
- Tool results kept separate from trusted system instructions
- Deep nesting (>5 levels) rejected
- Instruction-like content (imperative verbs at start) blocked

### 1.5 Output Sanitization

- Script tags (`<script>...</script>`) removed
- HTML tags (`<...>`) removed
- JavaScript event handlers (`onclick=`) removed
- Path traversal sequences (`../`) removed
- Internal path references (`/uploads/`, `/data/`, `storage_key`, `aegiscore.db`) redacted
- Secret patterns (`api_key=`, `secret=`, `password=`, `token=`) redacted

### 1.6 Audit Logging

- Tamper-evident append-only records with hash-chain integrity verification
- Each record links to previous via `chain_hash` (SHA-256)
- Tampering (modification, removal, reordering) breaks chain and is detectable
- Restricted write access recommended
- Safe logging — no sensitive document content or secrets in logs
- Sensitive fields (`resume_text`, `job_description`, `resume_summary`, `body`, `text`)
  redacted to length-only placeholders

### 1.7 Circuit Breaker

- Opens after 5 consecutive failures
- Half-open state allows trial execution after recovery timeout
- Successful trial closes circuit; failed trial reopens
- Prevents excessive subprocess restarts

### 1.8 Retry Budget

- Shared global deadline across MCP client, execution engine, and agent layers
- Total retry attempts capped (default 10)
- Prevents retry multiplication across layers
- Prevents excessive subprocess restarts

### 1.9 Output Limits

- Maximum output size: 1 MB default per tool
- Oversized outputs rejected with error (not silently truncated)
- Maximum concurrent executions: 5 default

### 1.10 Safe Fallback

- Direct V1 fallback permitted ONLY when it preserves same authorization,
  validation, citation, attachment integrity, and audit policies as MCP
- Fallback never bypasses security checks

---

## 2. Security Tests Executed (90 tests)

| Test File | Tests | Security Area |
|-----------|-------|-----------|
| test_mcp_tool_registry.py | 16 | Allowlist, schemas, permissions |
| test_mcp_audit_logger.py | 6 | Audit integrity, sensitive data |
| test_mcp_permission_engine.py | 12 | Confirm: true, attachment verification |
| test_mcp_execution_engine.py | 14 | Validation, timeouts, retries, budget |
| test_mcp_agent_integration.py | 8 | Output validation, capability mapping |
| test_mcp_circuit_breaker.py | 10 | Failure handling, recovery |
| test_mcp_prompt_injection_guard.py | 14 | Structural validation, sanitization |
| test_mcp_output_sanitizer.py | 10 | Script tags, path traversal, secrets |
| **Total** | **90** | |

---

## 3. Security Controls NOT Independently Verified

| Control | Reason |
|---------|--------|
| Restricted audit-log write access | File system permissions not tested in unit tests |
| No secrets in logs beyond redacted fields | Manual review only |
| Subprocess stderr doesn't leak secrets | Not explicitly tested |
| Circuit breaker under load | Not tested under concurrent failure conditions |

---

## 4. Known Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Audit log not absolutely immutable | Attacker with write access could rewrite chain | Restricted file permissions recommended |
| No OCR for scanned PDFs | Scanned PDFs report extraction failure | Documented limitation |
| No actual email delivery | Approval is workflow state only | Documented limitation |
| MCP server subprocess requires PYTHONPATH | Client must set PYTHONPATH to backend/app | Documented in setup |

---

## 5. Conclusion

Phase 2 MCP security controls are implemented and tested. All 90 security-related
tests pass. No critical or high-severity security defects identified. The
implementation enforces strict tool allowlisting, permission validation, attachment
integrity, prompt injection protection, output sanitization, audit logging, circuit
breaking, and safe fallback policies.

**No actual email is sent. No paid APIs are used. No OCR or image intelligence
features are implemented.**
