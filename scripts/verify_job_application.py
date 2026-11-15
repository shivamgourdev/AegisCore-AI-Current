"""Stage 2 Phase 7: Job Application Sandbox - complete browser workflow.
Tests the full email draft workflow via browser + API:
- Upload resume, generate draft, edit, save, approve
- Attachment integrity verification
- Approval immutability
- No email sent
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pymupdf
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BACKEND_BASE = "http://127.0.0.1:8000"
FRONTEND_BASE = "http://127.0.0.1:5500"


def main():
    results = []
    client = None

    def check(cond, msg):
        status = "PASS" if cond else "FAIL"
        line = f"[{status}] {msg}"
        results.append(line)
        print(line)
        if not cond:
            raise AssertionError(msg)

    try:
        client = httpx.Client(timeout=10.0)
        check(client.get(BACKEND_BASE + "/health").status_code == 200, "Backend health OK")
        check(client.get(FRONTEND_BASE + "/").status_code == 200, "Frontend reachable")

        data_dir = tempfile.mkdtemp(prefix="aegiscore-jobapp-")

        # Create resume PDF
        resume_path = Path(data_dir) / "resume.pdf"
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text((72, 72), "Shivam Gour\nPython Developer\nSkills: Python, FastAPI, SQL, RAG, Docker\nExperience: Built RAG systems with FastAPI and Ollama.\nEducation: B.S. Computer Science")
        pdf.save(str(resume_path))
        pdf.close()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: console_errors.append(str(exc)))

            # 1. Open application
            page.goto(FRONTEND_BASE + "/", wait_until="networkidle")

            # 2. Upload resume PDF
            file_input = page.locator("#resumeFile")
            file_input.set_input_files([str(resume_path)])
            page.locator("#uploadBtn").click()
            page.wait_for_timeout(5000)
            upload_status = page.locator("#uploadStatus").text_content()
            check("uploaded" in upload_status.lower(), f"Resume uploaded: {upload_status}")

            # 3. Get document ID from backend for verification
            docs_response = client.get(BACKEND_BASE + "/documents")
            docs_data = docs_response.json()
            resume_docs = [d for d in docs_data["documents"] if d["filename"] == "resume.pdf"]
            check(len(resume_docs) >= 1, "Resume registered in backend")
            resume_doc_id = resume_docs[0]["document_id"]
            resume_sha256 = resume_docs[0]["sha256"]

            # 4. Fill in job application form
            page.locator("#candidate").fill("Shivam Gour")
            page.locator("#recipient").fill("hr@example.com")
            page.locator("#jobTitle").fill("Python Developer")
            page.locator("#company").fill("Example Corp")
            page.locator("#summary").fill("Python developer with FastAPI, SQL, Docker, and RAG experience.")

            # 5. Generate draft
            page.locator("#draftBtn").click()
            page.wait_for_timeout(5000)

            draft_status = page.locator("#draftStatus").text_content()
            check("Draft saved" in draft_status, f"Draft generated: {draft_status}")
            check("Nothing has been sent" in draft_status, "Status says nothing sent")

            # 6. Verify draft via API
            draft_id_element = page.locator("#draftStatus").text_content()
            # Get draft ID from backend
            # The draft was just created, get it from the draft storage
            # We need to find it - let's check via the review attachment display
            review_attachment = page.locator("#reviewAttachment").text_content()
            check(resume_doc_id[:8] in review_attachment or resume_doc_id in review_attachment,
                  f"Attachment document ID shown: {review_attachment[:200]}")
            check(resume_sha256[:16] in review_attachment or resume_sha256 in review_attachment,
                  f"Attachment SHA-256 shown: {review_attachment[:200]}")

            # 7. Edit recipient
            page.locator("#reviewTo").fill("recruiter@example.com")
            page.wait_for_timeout(1000)
            check("Unsaved edits" in page.locator("#approvalStatus").text_content() or "changed" in page.locator("#approvalStatus").text_content().lower(),
                  "Unsaved edits detected after recipient change")

            # 8. Save changes
            page.locator("#saveDraftBtn").click()
            page.wait_for_timeout(5000)
            check("Changes saved" in page.locator("#approvalStatus").text_content(), "Changes saved")

            # 9. Verify draft updated via API
            # Get the draft ID from the page (it's displayed in draft status)
            # We'll verify by checking the draft can be retrieved
            # First, find the draft ID - it's in the draft status text
            draft_status_text = page.locator("#draftStatus").text_content()
            # The draft ID should be in the status text like "Draft ID: xxx"
            import re
            draft_id_match = re.search(r'Draft ID:\s*([^\s\n]+)', draft_status_text)
            if draft_id_match:
                draft_id = draft_id_match.group(1)
                get_draft = client.get(BACKEND_BASE + f"/jobs/email-drafts/{draft_id}")
                check(get_draft.status_code == 200, f"Draft retrievable via API: {get_draft.status_code}")
                draft_data = get_draft.json()
                check(draft_data["recipient_email"] == "recruiter@example.com", "Recipient updated in draft")
                check(draft_data["requires_user_approval"] is True, "Draft still requires approval after update")
                check(draft_data["sent"] is False, "Draft not sent")

            # 10. Verify attachment integrity
            check(draft_data.get("attachment_document_id") == resume_doc_id, "Draft binds correct resume attachment")
            check(draft_data.get("attachment_sha256") == resume_sha256, "Draft SHA-256 matches resume")

            # 11. Verify "No email is sent" message
            check("No email has been sent" in draft_status or "Nothing has been sent" in draft_status,
                  "Interface states no email sent")

            # 12. Check the disclaimer text
            disclaimer = page.locator("small").last.text_content()
            check("not send" in disclaimer.lower() or "not sent" in disclaimer.lower() or "no email" in disclaimer.lower(),
                  f"Disclaimer visible: {disclaimer[:200]}")

            # 13. Explicitly approve the draft
            page.locator("#confirm").check()
            page.wait_for_timeout(1000)
            check(page.locator("#approveBtn").is_enabled(), "Approve button enabled after confirmation")

            page.locator("#approveBtn").click()
            page.wait_for_timeout(5000)

            approval_status = page.locator("#approvalStatus").text_content()
            check("approved" in approval_status.lower(), f"Draft approved: {approval_status}")
            check("No email has been sent" in approval_status, "Approval confirms no email sent")

            # 14. Verify approved status via API
            if draft_id_match:
                approved_draft = client.get(BACKEND_BASE + f"/jobs/email-drafts/{draft_id}")
                check(approved_draft.status_code == 200, "Approved draft retrievable")
                approved_data = approved_draft.json()
                check(approved_data["status"] == "approved", "Draft status is approved")
                check(approved_data["requires_user_approval"] is False, "No longer requires approval")
                check(approved_data["sent"] is False, "Email not sent")
                # The approve POST response confirms "No email has been sent" message

            # 15. Verify approved draft cannot be modified (via API - UI correctly disables fields)
            if draft_id_match:
                tamper_update = client.put(
                    BACKEND_BASE + f"/jobs/email-drafts/{draft_id}",
                    json={
                        "recipient_email": "changed@example.com",
                        "subject": "Changed",
                        "body": "Changed body.",
                    },
                )
                check(tamper_update.status_code == 409, f"Approved draft modification rejected: {tamper_update.status_code}")

            # 16. Verify attachment tampering is rejected via API
            if draft_id_match:
                tamper_approve = client.post(
                    BACKEND_BASE + f"/jobs/email-drafts/{draft_id}/approve",
                    json={
                        "recipient_email": "recruiter@example.com",
                        "subject": "Tampered Subject",
                        "body": "Tampered body.",
                        "attachment_document_id": resume_doc_id,
                        "attachment_sha256": "0" * 64,  # Wrong SHA-256
                        "confirm": True,
                    },
                )
                check(tamper_approve.status_code == 409, f"Tampered attachment rejected: {tamper_approve.status_code}")

            # 17. Verify unknown attachment is rejected
            if draft_id_match:
                unknown_attach = client.post(
                    BACKEND_BASE + f"/jobs/email-drafts/{draft_id}/approve",
                    json={
                        "recipient_email": "recruiter@example.com",
                        "subject": "Test",
                        "body": "Test body.",
                        "attachment_document_id": "00000000-0000-0000-0000-000000000000",
                        "attachment_sha256": resume_sha256,
                        "confirm": True,
                    },
                )
                check(unknown_attach.status_code in (404, 409), f"Unknown attachment rejected: {unknown_attach.status_code}")

            # 18. Verify no actual email is sent
            check(approved_data.get("sent") is False, "Backend confirms email not sent")
            check("no email" in approval_status.lower(), "UI confirms email not sent")

            # Check no console errors
            check(len(console_errors) == 0, f"No console errors. Errors: {console_errors}")

            browser.close()

            # Check no console errors

        results.append("\n=== JOB APPLICATION SANDBOX VERIFICATION: ALL CHECKS PASSED ===")
        print("\n=== JOB APPLICATION SANDBOX VERIFICATION: ALL CHECKS PASSED ===")

    except Exception as exc:
        results.append(f"\n=== VERIFICATION FAILED: {type(exc).__name__}: {exc} ===")
        print(f"\n=== VERIFICATION FAILED: {type(exc).__name__}: {exc} ===")
        raise
    finally:
        if client is not None:
            client.close()
        import shutil
        try:
            shutil.rmtree(data_dir, ignore_errors=True)
        except Exception:
            pass

    evidence_path = ROOT / "evidence" / "part-10-job-application-browser-verification.txt"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("\n".join(results) + "\n", encoding="utf-8")
    print(f"\nEvidence written to: {evidence_path}")


if __name__ == "__main__":
    main()
