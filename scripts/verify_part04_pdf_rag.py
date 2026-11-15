import os
import sys
import time
import socket
import tempfile
import subprocess
from pathlib import Path

import httpx
import pymupdf

ROOT = Path.cwd()
EVIDENCE = ROOT / "evidence" / "part-04-pdf-rag-verification.txt"
EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
results = []
server = None
log_handle = None

def check(condition, message):
    if not condition:
        raise AssertionError(message)
    line = "PASS: " + message
    results.append(line)
    print(line)

try:
    pdf = pymupdf.open()
    page1 = pdf.new_page()
    page1.insert_text(
        (72, 72),
        "Northwind report. The office cafeteria serves lunch at noon."
    )
    page2 = pdf.new_page()
    page2.insert_text(
        (72, 72),
        "Project Cedar verification fact: the reserved test budget is "
        "73,500 credits for the October simulation."
    )
    pdf_bytes = pdf.tobytes()
    pdf.close()

    with tempfile.TemporaryDirectory(prefix="aegiscore-pdf-rag-") as data_dir:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        env = os.environ.copy()
        env["AEGISCORE_DATA_DIR"] = data_dir
        env["PYTHONPATH"] = str(ROOT / "backend" / "app")

        log_path = ROOT / "evidence" / "part-04-pdf-rag-uvicorn.log"
        log_handle = open(log_path, "w", encoding="utf-8")

        server = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "aegiscore.main:app",
                "--host", "127.0.0.1",
                "--port", str(port),
            ],
            cwd=str(ROOT / "backend" / "app"),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )

        base = f"http://127.0.0.1:{port}"
        client = httpx.Client(timeout=200.0)

        try:
            ready = False
            for _ in range(60):
                if server.poll() is not None:
                    raise RuntimeError(
                        f"Uvicorn exited early; inspect {log_path}"
                    )
                try:
                    if client.get(base + "/health").status_code == 200:
                        ready = True
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.5)

            check(ready, "Live Uvicorn health endpoint returns HTTP 200")

            upload = client.post(
                base + "/documents/upload",
                files={
                    "file": (
                        "pdf-page-proof.pdf",
                        pdf_bytes,
                        "application/pdf",
                    )
                },
            )
            check(upload.status_code == 200, f"PDF upload succeeds: {upload.text[:400]}")
            body = upload.json()
            check(
                body.get("extraction", {}).get("status") == "text_extracted",
                "PDF extraction reports text_extracted",
            )
            check(
                body.get("extraction", {}).get("page_count") == 2,
                "PDF extraction identifies both pages",
            )

            document_id = body["document"]["document_id"]
            extraction_response = client.get(
                base + f"/documents/{document_id}/extraction"
            )
            check(
                extraction_response.status_code == 200,
                "Persisted PDF extraction is readable through the API",
            )
            extraction = extraction_response.json()
            pages = extraction.get("pages", [])

            check(
                [p.get("page_number") for p in pages] == [1, 2],
                f"PDF preserves one-based page numbers: {[p.get('page_number') for p in pages]}",
            )
            check(
                "73,500 credits" in pages[1].get("text", ""),
                "Unique evidence is extracted from actual PDF page 2",
            )

            chunks_response = client.get(
                base + f"/documents/{document_id}/chunks"
            )
            check(chunks_response.status_code == 200, "PDF chunks are available")
            chunks = chunks_response.json().get("chunks", [])
            check(
                any(
                    c.get("page_number") == 2
                    and "73,500 credits" in c.get("text", "")
                    for c in chunks
                ),
                "Chunking preserves page 2 and its unique evidence",
            )

            embedded = client.post(base + f"/documents/{document_id}/embed")
            check(
                embedded.status_code == 200,
                f"Live Ollama embedding succeeds: {embedded.text[:400]}",
            )
            check(
                embedded.json().get("embedding_count", 0) > 0,
                "PDF chunk embeddings are persisted",
            )

            response = client.post(
                base + "/ask",
                json={
                    "query": "What is the reserved test budget for Project Cedar?",
                    "top_k": 5,
                    "min_similarity": 0.35,
                },
            )
            check(response.status_code == 200, f"PDF RAG question returns HTTP 200: {response.text[:500]}")
            answer = response.json()
            print("PDF RAG ANSWER:", answer)

            check(answer.get("abstained") is False, "PDF RAG answers the supported question")
            check(
                "73,500" in answer.get("answer", "")
                and "credits" in answer.get("answer", "").lower(),
                "Answer preserves the exact supported amount and unit",
            )

            citations = answer.get("citations", [])
            check(bool(citations), "PDF RAG answer includes citations")
            check(
                any(c.get("filename") == "pdf-page-proof.pdf" for c in citations),
                "Citation identifies the uploaded PDF filename",
            )
            check(
                any(c.get("page_number") == 2 for c in citations),
                "Citation points to the correct PDF page 2",
            )
            check(
                any(
                    c.get("page_number") == 2
                    and "73,500 credits" in c.get("text", "")
                    for c in citations
                ),
                "Page 2 citation passage contains the exact supporting evidence",
            )
            for citation in citations:
                check(
                    citation.get("source_id")
                    and f"[{citation['source_id']}]" in answer.get("answer", ""),
                    "Each returned citation ID is referenced in the answer",
                )

            unknown = client.post(
                base + "/ask",
                json={
                    "query": "What is the secret launch code for Project Zephyr?",
                    "top_k": 5,
                    "min_similarity": 1.0,
                },
            )
            check(unknown.status_code == 200, "Unsupported PDF question returns HTTP 200")
            unknown_body = unknown.json()
            check(
                unknown_body.get("abstained") is True,
                "Unsupported PDF question is explicitly abstained",
            )
            check(
                unknown_body.get("citations") == [],
                "Unsupported PDF question returns no citations",
            )

        finally:
            client.close()

    results.append("LIVE PDF-TO-RAG VERIFICATION: PASS")
    print("LIVE PDF-TO-RAG VERIFICATION: PASS")

except Exception as exc:
    results.append(f"FAIL: {type(exc).__name__}: {exc}")
    print(f"FAIL: {type(exc).__name__}: {exc}")
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

    EVIDENCE.write_text("\n".join(results) + "\n", encoding="utf-8")
    print(f"Evidence written to: {EVIDENCE}")
