import os
import sys
import time
import socket
import tempfile
import subprocess
from pathlib import Path

import httpx
import pymupdf

root = Path.cwd()
evidence = root / "evidence" / "part-03b-live-api-verification.txt"
results = []
server = None
log_handle = None

def check(condition, message):
    if not condition:
        raise AssertionError(message)
    results.append("PASS: " + message)
    print("PASS:", message)

try:
    with tempfile.TemporaryDirectory(prefix="aegiscore-verify-") as data_dir:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        env = os.environ.copy()
        env["AEGISCORE_DATA_DIR"] = data_dir
        env["PYTHONPATH"] = str(root / "backend" / "app")
        log_path = root / "evidence" / "part-03b-uvicorn.log"
        log_handle = open(log_path, "w", encoding="utf-8")

        server = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "aegiscore.main:app",
                "--host", "127.0.0.1", "--port", str(port),
            ],
            cwd=str(root / "backend" / "app"),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )

        base = f"http://127.0.0.1:{port}"
        client = httpx.Client(timeout=10.0)
        try:
            ready = False
            for _ in range(60):
                if server.poll() is not None:
                    raise RuntimeError("Uvicorn exited early. Check part-03b-uvicorn.log")
                try:
                    response = client.get(base + "/health")
                    if response.status_code == 200:
                        ready = True
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.5)

            check(ready, "Real Uvicorn server starts and /health responds HTTP 200")
            check(client.get(base + "/").status_code == 200,
                  "Root endpoint responds HTTP 200")
            check(client.get(base + "/openapi.json").status_code == 200,
                  "Live OpenAPI schema is reachable")

            text_bytes = b"AegisCore live verification document. Source sentence for retrieval."
            first = client.post(
                base + "/documents/upload",
                files={"file": ("live-check.txt", text_bytes, "text/plain")},
            )
            check(first.status_code == 200, "Live TXT upload responds HTTP 200")
            first_data = first.json()
            document = first_data.get("document", {})
            doc_id = document.get("document_id")
            check(bool(doc_id), "TXT upload returns a document ID")
            check(first_data.get("extraction", {}).get("status") == "text_extracted",
                  "TXT upload triggers successful extraction")

            extracted = client.get(base + f"/documents/{doc_id}/extraction")
            check(extracted.status_code == 200, "Stored extraction endpoint responds HTTP 200")
            extraction_data = extracted.json()
            check("Source sentence for retrieval" in extraction_data.get("text", ""),
                  "Extracted text persists and can be read back")

            duplicate = client.post(
                base + "/documents/upload",
                files={"file": ("live-check.txt", text_bytes, "text/plain")},
            )
            check(duplicate.status_code == 200, "Repeated TXT upload is handled")
            duplicate_data = duplicate.json()
            check(duplicate_data.get("duplicate") is True,
                  "Repeated identical content is identified as duplicate")
            check(duplicate_data.get("document", {}).get("document_id") == doc_id,
                  "Duplicate upload reuses the original document ID")

            pdf_doc = pymupdf.open()
            page1 = pdf_doc.new_page()
            page1.insert_text((72, 72), "AegisCore PDF live verification page one.")
            page2 = pdf_doc.new_page()
            page2.insert_text((72, 72), "AegisCore PDF live verification page two.")
            pdf_bytes = pdf_doc.tobytes()
            pdf_doc.close()

            pdf_response = client.post(
                base + "/documents/upload",
                files={"file": ("live-check.pdf", pdf_bytes, "application/pdf")},
            )
            check(pdf_response.status_code == 200, "Live PDF upload responds HTTP 200")
            pdf_data = pdf_response.json()
            pdf_id = pdf_data.get("document", {}).get("document_id")
            check(bool(pdf_id), "PDF upload returns a document ID")
            check(pdf_data.get("extraction", {}).get("status") == "text_extracted",
                  "Live PDF text extraction succeeds")

            pdf_extraction = client.get(base + f"/documents/{pdf_id}/extraction")
            check(pdf_extraction.status_code == 200, "PDF extraction is readable through API")
            pages = pdf_extraction.json().get("pages", [])
            page_numbers = [p.get("page_number") for p in pages]
            check(page_numbers == [1, 2], "PDF extraction preserves source page numbers")
            pdf_text = " ".join(p.get("text", "") for p in pages)
            check("page one" in pdf_text and "page two" in pdf_text,
                  "Text from both PDF pages is preserved")

            listing = client.get(base + "/documents")
            check(listing.status_code == 200, "Document listing responds HTTP 200")
            listing_data = listing.json()
            docs = listing_data.get("documents", []) if isinstance(listing_data, dict) else listing_data
            listed_ids = {d.get("document_id") for d in docs if isinstance(d, dict)}
            check(doc_id in listed_ids and pdf_id in listed_ids,
                  "Uploaded documents appear in the document listing")
        finally:
            client.close()

    results.append("LIMITATION: OCR, RAG answer generation and answer citations are not verified by this check.")
    results.append("FINAL RESULT: PASS")
except Exception as exc:
    results.append("FAIL: " + repr(exc))
    results.append("FINAL RESULT: FAIL")
    print("FAIL:", repr(exc))
    raise
finally:
    if server is not None and server.poll() is None:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
    if log_handle is not None:
        log_handle.close()
    evidence.write_text("\n".join(results) + "\n", encoding="utf-8")
    print("\nEvidence written to:", evidence)
