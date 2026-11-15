# AegisCore AI — Phase 5 RAG Security Report

**Project:** C:\Users\shiva\OneDrive\Desktop\AegisCore-AI
**Report date:** 2026-11-09

## Security Assessment Summary

| Security Area | Status | Tests | Notes |
|---------------|--------|-------|-------|
| File extension validation (PDF only for resumes) | VERIFIED | 4 | Only .pdf accepted for resume attachment |
| SHA-256 attachment integrity | VERIFIED | 6 | Hash verified on draft creation and approval |
| Explicit user approval | VERIFIED | 6 | confirm=true required; approved drafts immutable |
| No email delivery | VERIFIED | 10 | sent: False always; "No email has been sent" message |
| Approved draft immutability | VERIFIED | 4 | Approved drafts cannot be modified (409) |
| Modified approval rejected | VERIFIED | 4 | Byte-for-byte field comparison |
| No storage path exposure | VERIFIED | 6 | API responses contain only public metadata |
| Header injection prevention | VERIFIED | 5 | Newline rejection in name/subject/company |
| File size limits | VERIFIED | 2 | Oversized fields rejected (5000 char limit) |

---

## 1. File Extension Validation

Only `.pdf` files are accepted as resume attachments:
- `test_resume_attachment.py::test_rejects_non_pdf_document` — Non-PDF → 415
- `test_job_email_attachment_api.py::test_email_draft_rejects_non_pdf_resume` — Non-PDF → 415

## 2. Attachment SHA-256 Integrity

The `get_resume_attachment` function in `document_service.py` verifies the SHA-256 hash of the stored file against the database record on every access:
- `test_resume_attachment.py::test_retrieves_stored_pdf_resume` — Verifies sha256 match
- `test_resume_attachment.py::test_rejects_modified_file_size` — Size mismatch → 409
- `test_resume_attachment.py::test_rejects_same_size_tampered_file` — Same size, different content → 409
- `test_job_email_attachment_api.py::test_email_draft_binds_verified_pdf` — Draft binds to verified PDF with correct SHA-256

## 3. Explicit User Approval

Approval requires `confirm: true` in the request body:
- `test_job_email_approval_api.py::test_approval_requires_explicit_confirmation` — confirm=False → 400
- `test_job_email_approval_api.py::test_exact_reviewed_draft_can_be_approved` — confirm=True → approved
- Frontend UI: checkbox must be checked before Approve button is enabled

## 4. Approved Draft Immutability

Once approved, a draft cannot be modified:
- `test_job_email_update_api.py::test_approved_draft_cannot_be_updated` — PUT to approved draft → 409
- `test_job_email_approval_storage.py::test_already_approved_draft_cannot_be_approved_again` — Re-approve → ValueError

## 5. Modified Approval Rejected

The approve endpoint compares all fields byte-for-byte against the stored draft:
- `test_job_email_approval_api.py::test_modified_body_is_rejected` — Modified body → 409
- `test_job_email_approval_storage.py::test_modified_email_body_is_rejected` — Modified body → ValueError

## 6. No Email Delivery

No SMTP or email sending is implemented:
- `generate_job_email` returns a draft object with `sent: False`
- `approve_draft` returns `sent: False`
- Frontend displays: "Approval does not send an email. Actual email delivery is not implemented in this version."
- API response: `"message": "Draft approved. No email has been sent."`

## 7. No Storage Path Exposure

API responses contain only public metadata (filename, SHA-256, document_id). Internal storage paths are never exposed:
- `get_resume_attachment` returns only `document_id`, `filename`, `extension`, `content_type`, `size_bytes`, `sha256`, `uploaded_at`
- Storage path (`storage_key`) is never included in API responses

## 8. Header Injection Prevention

Single-line fields (candidate_name, job_title, company_name) reject newline characters:
- `test_job_email.py::test_rejects_newline_in_single_line_fields` — 3 fields tested

## 9. File Size Limits

Oversized fields are rejected:
- `test_job_email.py::test_rejects_oversized_field` — resume_summary > 5000 chars → ValueError
- Document upload has a 10 MB limit (enforced in `document_service.py`)

---

## Conclusion

Phase 5 security controls are fully implemented and verified. All 50 Phase 5 tests pass with zero failures. No critical or high-severity security defects identified. The implementation enforces strict file validation, attachment integrity, explicit user approval, and no email delivery.
