"""Stage 2: Real-server verification for document status and delete endpoints.
Starts a live Uvicorn server with an isolated temp data directory and tests:
- GET /documents/{id}/status for existing, unknown, and after-embedding documents
- DELETE /documents/{id} for chunk/embedding/extraction/file cleanup
- Cross-document isolation (deleting one doesn't affect another)
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

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
        data_dir = tempfile.mkdtemp(prefix="aegiscore-stage2-")
        port = _find_free_port()
        log_path = Path(data_dir) / "uvicorn.log"
        log_handle = open(log_path, "w", encoding="utf-8")

        server = _start_server(port, data_dir, log_handle)
        base = f"http://127.0.0.1:{port}"
        client = _wait_for_health(base)

        check(client.get(base + "/health").status_code == 200, "Health endpoint OK")

        # --- Upload a TXT document ---
        txt_upload = client.post(
            base + "/documents/upload",
            files={"file": ("notes.txt", b"Project Orion revenue was 42 million dollars in Q3. The hiring team plans to recruit six junior Python engineers.", "text/plain")},
        )
        check(txt_upload.status_code == 200, f"TXT upload OK: {txt_upload.status_code}")
        txt_doc_id = txt_upload.json()["document"]["document_id"]

        # --- Embed it ---
        txt_embed = client.post(base + f"/documents/{txt_doc_id}/embed")
        check(txt_embed.status_code == 200, f"TXT embed OK: {txt_embed.status_code}")

        # --- Upload a PDF document ---
        import pymupdf
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text((72, 72), "Unique fact on page 2: The moon base will launch in 2030.")
        pdf_bytes = pdf.tobytes()
        pdf.close()
        pdf_upload = client.post(
            base + "/documents/upload",
            files={"file": ("moon.pdf", pdf_bytes, "application/pdf")},
        )
        check(pdf_upload.status_code == 200, f"PDF upload OK: {pdf_upload.status_code}")
        pdf_doc_id = pdf_upload.json()["document"]["document_id"]
        pdf_embed = client.post(base + f"/documents/{pdf_doc_id}/embed")
        check(pdf_embed.status_code == 200, f"PDF embed OK: {pdf_embed.status_code}")

        # ===== STATUS ENDPOINT TESTS =====

        # Status for TXT doc (embedded)
        txt_status = client.get(base + f"/documents/{txt_doc_id}/status")
        check(txt_status.status_code == 200, f"TXT status OK: {txt_status.status_code}")
        txt_status_data = txt_status.json()
        check(txt_status_data["document_id"] == txt_doc_id, "TXT status document_id matches")
        check(txt_status_data["filename"] == "notes.txt", "TXT status filename matches")
        check(txt_status_data["extension"] == ".txt", "TXT status extension matches")
        check(txt_status_data["status"] == "text_extracted", "TXT status is text_extracted")
        check(txt_status_data["page_count"] >= 1, "TXT page_count >= 1")
        check(txt_status_data["chunk_count"] >= 1, "TXT chunk_count >= 1")
        check(txt_status_data["embedding_count"] >= 1, "TXT embedding_count >= 1")
        check(txt_status_data["embedding_model"] is not None, "TXT embedding_model set")

        # Status for PDF doc (embedded)
        pdf_status = client.get(base + f"/documents/{pdf_doc_id}/status")
        check(pdf_status.status_code == 200, f"PDF status OK: {pdf_status.status_code}")
        pdf_status_data = pdf_status.json()
        check(pdf_status_data["document_id"] == pdf_doc_id, "PDF status document_id matches")
        check(pdf_status_data["filename"] == "moon.pdf", "PDF status filename matches")
        check(pdf_status_data["extension"] == ".pdf", "PDF status extension matches")
        check(pdf_status_data["status"] == "text_extracted", "PDF status is text_extracted")
        check(pdf_status_data["page_count"] >= 1, "PDF page_count >= 1")
        check(pdf_status_data["chunk_count"] >= 1, "PDF chunk_count >= 1")
        check(pdf_status_data["embedding_count"] >= 1, "PDF embedding_count >= 1")

        # Status for unknown document
        unknown_status = client.get(
            base + "/documents/00000000-0000-0000-0000-000000000000/status"
        )
        check(unknown_status.status_code == 404, "Unknown document status returns 404")

        # Status for uploaded-but-not-embedded document
        not_embedded = client.post(
            base + "/documents/upload",
            files={"file": ("plain.txt", b"No embeddings yet.", "text/plain")},
        )
        check(not_embedded.status_code == 200, "Plain upload OK")
        plain_doc_id = not_embedded.json()["document"]["document_id"]
        plain_status = client.get(base + f"/documents/{plain_doc_id}/status")
        check(plain_status.status_code == 200, "Plain status OK")
        plain_data = plain_status.json()
        check(plain_data["chunk_count"] >= 1, "Plain has chunks")
        check(plain_data["embedding_count"] == 0, "Plain has zero embeddings")

        # ===== DELETE ENDPOINT TESTS =====

        # Delete the plain (not embedded) document
        plain_delete = client.delete(base + f"/documents/{plain_doc_id}")
        check(plain_delete.status_code == 200, f"Plain delete OK: {plain_delete.status_code}")
        check(plain_delete.json()["deleted"] is True, "Plain deleted flag true")
        plain_status_after = client.get(base + f"/documents/{plain_doc_id}/status")
        check(plain_status_after.status_code == 404, "Plain status 404 after delete")

        # Delete the PDF document (has embeddings)
        pdf_delete = client.delete(base + f"/documents/{pdf_doc_id}")
        check(pdf_delete.status_code == 200, f"PDF delete OK: {pdf_delete.status_code}")
        check(pdf_delete.json()["deleted"] is True, "PDF deleted flag true")
        pdf_status_after = client.get(base + f"/documents/{pdf_doc_id}/status")
        check(pdf_status_after.status_code == 404, "PDF status 404 after delete")
        pdf_chunks_after = client.get(base + f"/documents/{pdf_doc_id}/chunks")
        check(pdf_chunks_after.status_code == 404, "PDF chunks 404 after delete")
        pdf_embeddings_after = client.get(base + f"/documents/{pdf_doc_id}/embeddings")
        check(pdf_embeddings_after.status_code == 404, "PDF embeddings 404 after delete")

        # Delete unknown document
        unknown_delete = client.delete(
            base + "/documents/00000000-0000-0000-0000-000000000000"
        )
        check(unknown_delete.status_code == 404, "Unknown document delete returns 404")

        # Cross-document isolation: TXT doc should still exist after deleting others
        txt_still_exists = client.get(base + f"/documents/{txt_doc_id}/status")
        check(txt_still_exists.status_code == 200, "TXT doc still exists after other deletes")
        txt_embeddings = client.get(base + f"/documents/{txt_doc_id}/embeddings")
        check(txt_embeddings.status_code == 200, "TXT embeddings still available")

        # Clean up TXT doc too
        txt_delete = client.delete(base + f"/documents/{txt_doc_id}")
        check(txt_delete.status_code == 200, "Final TXT delete OK")

        results.append("\n=== DOCUMENT STATUS AND DELETE VERIFICATION: ALL CHECKS PASSED ===")
        print("\n=== DOCUMENT STATUS AND DELETE VERIFICATION: ALL CHECKS PASSED ===")

    except Exception as exc:
        results.append(f"\n=== VERIFICATION FAILED: {type(exc).__name__}: {exc} ===")
        print(f"\n=== VERIFICATION FAILED: {type(exc).__name__}: {exc} ===")
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
            import shutil
            shutil.rmtree(data_dir, ignore_errors=True)

    # Write evidence
    evidence_path = ROOT / "evidence" / "part-06-status-delete-verification.txt"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("\n".join(results) + "\n", encoding="utf-8")
    print(f"\nEvidence written to: {evidence_path}")


if __name__ == "__main__":
    main()
