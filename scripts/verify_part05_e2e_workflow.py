"""End-to-end API verification for all AegisCore AI workflows.
Starts a real Uvicorn server and exercises every API route.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "backend" / "app"


def _find_free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_server(port, data_dir, log_handle):
    env = os.environ.copy()
    env["AEGISCORE_DATA_DIR"] = str(data_dir)
    env["PYTHONPATH"] = str(APP_DIR)
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "aegiscore.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(APP_DIR),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )


def _wait_for_health(base, timeout=30):
    client = httpx.Client(timeout=10.0)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if client.get(base + "/health").status_code == 200:
                return client
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    client.close()
    raise RuntimeError("Server did not become healthy")


def _make_pdf(texts):
    pdf = pymupdf.open()
    for text in texts:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    data = pdf.tobytes()
    pdf.close()
    return data


def main():
    results = []
    server = None
    client = None
    log_handle = None
    data_dir = None

    def check(cond, msg):
        status = "PASS" if cond else "FAIL"
        line = f"[{status}] {msg}"
        results.append(line)
        print(line)
        if not cond:
            raise AssertionError(msg)

    try:
        data_dir = tempfile.mkdtemp(prefix="aegiscore-e2e-")
        port = _find_free_port()
        log_path = Path(data_dir) / "uvicorn.log"
        log_handle = open(log_path, "w", encoding="utf-8")

        server = _start_server(port, data_dir, log_handle)
        base = f"http://127.0.0.1:{port}"
        client = _wait_for_health(base)

        check(client.get(base + "/health").status_code == 200, "Health endpoint OK")
        check(client.get(base + "/").status_code == 200, "Root endpoint OK")

        # --- Resume upload (PDF) ---
        pdf_bytes = _make_pdf([
            "Shivam Gour\nPython Developer\nSkills: Python, FastAPI, SQL, RAG, Docker",
            "Experience: Built RAG systems with FastAPI and Ollama.",
        ])
        upload = client.post(
            base + "/documents/upload",
            files={"file": ("shivam_resume.pdf", pdf_bytes, "application/pdf")},
        )
        check(upload.status_code == 200, f"Resume PDF upload: {upload.status_code}")
        upload_data = upload.json()
        resume_doc_id = upload_data["document"]["document_id"]
        check(upload_data["duplicate"] is False, "Resume is not a duplicate")
        check(upload_data["extraction"]["status"] == "text_extracted",
              "Resume text extracted")

        # --- Get extraction text ---
        ext = client.get(base + f"/documents/{resume_doc_id}/extraction")
        check(ext.status_code == 200, "Extraction endpoint OK")
        ext_data = ext.json()
        check("Shivam Gour" in ext_data["text"], "Resume text contains name")
        check("Python" in ext_data["text"], "Resume text contains skills")
        check(len(ext_data["pages"]) == 2, "Resume has 2 pages")

        # --- Get chunks ---
        chunks = client.get(base + f"/documents/{resume_doc_id}/chunks")
        check(chunks.status_code == 200, "Chunks endpoint OK")
        check(chunks.json()["chunk_count"] >= 1, "Chunks exist")

        # --- Embed chunks ---
        embed = client.post(base + f"/documents/{resume_doc_id}/embed")
        check(embed.status_code == 200, f"Embedding OK: {embed.status_code}")
        embed_data = embed.json()
        check(embed_data["embedding_count"] >= 1, "Embeddings created")

        # --- Semantic search ---
        search = client.post(base + "/search", json={
            "query": "Python FastAPI RAG", "top_k": 5, "mode": "dense"
        })
        check(search.status_code == 200, "Dense search OK")
        search_data = search.json()
        check(search_data["mode"] == "dense", "Dense mode returned")
        check(len(search_data["results"]) >= 1, "Search results exist")

        # --- Sparse search ---
        search_sparse = client.post(base + "/search", json={
            "query": "Python FastAPI RAG", "top_k": 5, "mode": "sparse"
        })
        check(search_sparse.status_code == 200, "Sparse search OK")
        check(search_sparse.json()["mode"] == "sparse", "Sparse mode returned")

        # --- Hybrid search ---
        search_hybrid = client.post(base + "/search", json={
            "query": "Python FastAPI RAG", "top_k": 5, "mode": "hybrid"
        })
        check(search_hybrid.status_code == 200, "Hybrid search OK")
        check(search_hybrid.json()["mode"] == "hybrid", "Hybrid mode returned")

        # --- RAG QA ---
        ask = client.post(base + "/ask", json={
            "query": "What skills does Shivam have?",
            "top_k": 5, "min_similarity": 0.30,
        }, timeout=120.0)
        check(ask.status_code == 200, f"RAG QA OK: {ask.status_code}")
        ask_data = ask.json()
        check(ask_data["abstained"] is False, "RAG QA not abstained")
        check(len(ask_data["citations"]) >= 1, "RAG QA has citations")
        check("Python" in ask_data["answer"], "Answer mentions Python")

        # --- Job analysis ---
        analysis = client.post(base + "/jobs/analyze", json={
            "resume_text": "Python, FastAPI, SQL, RAG, Docker experience.",
            "job_description": "We need Python, SQL, Docker, Machine Learning.",
        })
        check(analysis.status_code == 200, f"Job analysis OK: {analysis.status_code}")
        analysis_data = analysis.json()
        check("Python" in analysis_data["matched_skills"], "Python matched")
        check("Machine Learning" in analysis_data["missing_skills"], "ML missing")
        check(analysis_data["match_percentage"] == 75, "Match percentage 75%")

        # --- Create email draft ---
        draft_payload = {
            "candidate_name": "Shivam Gour",
            "recipient_email": "hr@example.com",
            "job_title": "Python Developer",
            "company_name": "Example Corp",
            "resume_summary": "Python, FastAPI and RAG experience.",
            "resume_document_id": resume_doc_id,
        }
        draft = client.post(base + "/jobs/email-draft", json=draft_payload)
        check(draft.status_code == 200, f"Draft creation OK: {draft.status_code}")
        draft_data = draft.json()
        draft_id = draft_data["draft_id"]
        check(draft_data["status"] == "pending", "Draft is pending")
        check(draft_data["requires_user_approval"] is True, "Requires approval")
        check(draft_data["sent"] is False, "Not sent")
        check(draft_data["attachment_document_id"] == resume_doc_id,
              "Draft binds resume attachment")
        check(draft_data["attachment_filename"] == "shivam_resume.pdf",
              "Draft has correct filename")

        # --- Get draft ---
        get_draft_resp = client.get(base + f"/jobs/email-drafts/{draft_id}")
        check(get_draft_resp.status_code == 200, "Get draft OK")
        check(get_draft_resp.json()["draft_id"] == draft_id, "Draft ID matches")

        # --- Update draft ---
        update = client.put(
            base + f"/jobs/email-drafts/{draft_id}",
            json={
                "recipient_email": "recruiter@example.com",
                "subject": "Updated Application",
                "body": "Dear Recruiter, please review my application.",
            },
        )
        check(update.status_code == 200, f"Draft update OK: {update.status_code}")
        update_data = update.json()
        check(update_data["recipient_email"] == "recruiter@example.com",
              "Recipient updated")
        check(update_data["status"] == "pending", "Still pending after update")
        check(update_data["requires_user_approval"] is True,
              "Still requires approval after update")

        # --- Approve draft ---
        approve = client.post(
            base + f"/jobs/email-drafts/{draft_id}/approve",
            json={
                "recipient_email": "recruiter@example.com",
                "subject": "Updated Application",
                "body": "Dear Recruiter, please review my application.",
                "attachment_document_id": resume_doc_id,
                "attachment_sha256": upload_data["document"]["sha256"],
                "confirm": True,
            },
        )
        check(approve.status_code == 200, f"Draft approval OK: {approve.status_code}")
        approve_data = approve.json()
        check(approve_data["status"] == "approved", "Draft is approved")
        check(approve_data["requires_user_approval"] is False,
              "No longer requires approval")
        check(approve_data["sent"] is False, "Email not sent")
        check("No email has been sent" in approve_data["message"],
              "Message confirms no email sent")

        # --- Verify approved draft cannot be updated ---
        update_again = client.put(
            base + f"/jobs/email-drafts/{draft_id}",
            json={
                "recipient_email": "changed@example.com",
                "subject": "Changed",
                "body": "Changed body.",
            },
        )
        check(update_again.status_code == 409,
              "Approved draft cannot be updated")

        # --- Verify modified approval is rejected ---
        bad_approve = client.post(
            base + f"/jobs/email-drafts/{draft_id}/approve",
            json={
                "recipient_email": "recruiter@example.com",
                "subject": "Updated Application",
                "body": "Tampered body.",
                "attachment_document_id": resume_doc_id,
                "attachment_sha256": upload_data["document"]["sha256"],
                "confirm": True,
            },
        )
        check(bad_approve.status_code == 409,
              "Modified approval rejected")

        # --- Verify confirmation required ---
        no_confirm = client.post(
            base + f"/jobs/email-drafts/{draft_id}/approve",
            json={
                "recipient_email": "recruiter@example.com",
                "subject": "Updated Application",
                "body": "Dear Recruiter, please review my application.",
                "attachment_document_id": resume_doc_id,
                "attachment_sha256": upload_data["document"]["sha256"],
                "confirm": False,
            },
        )
        check(no_confirm.status_code == 400,
              "Approval without confirm rejected")

        # --- Unknown resume rejected ---
        bad_draft = client.post(base + "/jobs/email-draft", json={
            **draft_payload,
            "resume_document_id": "unknown-id",
        })
        check(bad_draft.status_code == 404,
              "Unknown resume rejected for draft")

        # --- Non-PDF resume rejected ---
        txt_doc = client.post(
            base + "/documents/upload",
            files={"file": ("notes.txt", b"Text resume", "text/plain")},
        )
        txt_doc_id = txt_doc.json()["document"]["document_id"]
        bad_txt_draft = client.post(base + "/jobs/email-draft", json={
            **draft_payload,
            "resume_document_id": txt_doc_id,
        })
        check(bad_txt_draft.status_code == 415,
              "Non-PDF resume rejected for draft")

        # --- Unsupported extension rejected ---
        bad_upload = client.post(
            base + "/documents/upload",
            files={"file": ("malware.exe", b"binary", "application/octet-stream")},
        )
        check(bad_upload.status_code == 415, "Unsupported extension rejected")

        # --- Oversized upload rejected ---
        big = client.post(
            base + "/documents/upload",
            files={"file": ("big.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain")},
        )
        check(big.status_code == 413, "Oversized upload rejected")

        # --- List documents ---
        docs = client.get(base + "/documents")
        check(docs.status_code == 200, "List documents OK")
        check(len(docs.json()["documents"]) >= 2, "Multiple documents listed")

        # --- Document not found ---
        not_found = client.get(
            base + "/documents/00000000-0000-0000-0000-000000000000/chunks"
        )
        check(not_found.status_code == 404, "Unknown document returns 404")

        results.append("\n=== END-TO-END VERIFICATION: ALL CHECKS PASSED ===")
        print("\n=== END-TO-END VERIFICATION: ALL CHECKS PASSED ===")

    except Exception as exc:
        results.append(f"\n=== END-TO-END VERIFICATION FAILED: {type(exc).__name__}: {exc} ===")
        print(f"\n=== END-TO-END VERIFICATION FAILED: {type(exc).__name__}: {exc} ===")
        raise
    finally:
        if client is not None:
            client.close()
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        if log_handle is not None:
            log_handle.close()
        if data_dir is not None:
            try:
                shutil.rmtree(data_dir, ignore_errors=True)
            except Exception:
                pass

    # Write evidence
    evidence_path = ROOT / "evidence" / "part-05-e2e-workflow-verification.txt"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("\n".join(results) + "\n", encoding="utf-8")
    print(f"\nEvidence written to: {evidence_path}")


if __name__ == "__main__":
    main()
