import os
import sys
import time
import socket
import tempfile
import subprocess
from pathlib import Path

import httpx

ROOT = Path.cwd()
EVIDENCE = ROOT / "evidence" / "part-04f-live-rag-api-verification.txt"
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
    with tempfile.TemporaryDirectory(prefix="aegiscore-live-rag-") as data_dir:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        env = os.environ.copy()
        env["AEGISCORE_DATA_DIR"] = data_dir
        env["PYTHONPATH"] = str(ROOT / "backend" / "app")
        log_path = ROOT / "evidence" / "part-04f-uvicorn.log"
        log_handle = open(log_path, "w", encoding="utf-8")

        server = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "aegiscore.main:app",
                "--host", "127.0.0.1", "--port", str(port),
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

            check(ready, "Real Uvicorn server starts and health returns HTTP 200")

            documents = [
                (
                    "finance-live.txt",
                    "Project Orion revenue was 42 million dollars in Q3. "
                    "The finance report identifies this as quarterly revenue."
                ),
                (
                    "hiring-live.txt",
                    "The hiring team plans to recruit six junior Python engineers. "
                    "The planned hiring total is six engineers."
                ),
            ]

            doc_ids = {}
            for filename, content in documents:
                response = client.post(
                    base + "/documents/upload",
                    files={"file": (filename, content.encode("utf-8"), "text/plain")},
                )
                check(response.status_code == 200, f"Live upload succeeds: {filename}")
                body = response.json()
                check(
                    body.get("extraction", {}).get("status") == "text_extracted",
                    f"Text extraction succeeds: {filename}",
                )
                doc_id = body.get("document", {}).get("document_id")
                check(bool(doc_id), f"Upload returns document ID: {filename}")
                doc_ids[filename] = doc_id

                embedded = client.post(base + f"/documents/{doc_id}/embed")
                check(
                    embedded.status_code == 200,
                    f"Live Ollama embedding succeeds: {filename}; "
                    f"response={embedded.text[:300]}",
                )
                embedding_body = embedded.json()
                check(
                    embedding_body.get("embedding_count", 0) > 0,
                    f"Persisted embeddings exist: {filename}",
                )

            check(len(doc_ids) == 2, "Two distinct documents are ready for RAG")

            finance = client.post(
                base + "/ask",
                json={"query": "What was Project Orion's revenue in Q3?",
                      "top_k": 5, "min_similarity": 0.45},
            )
            check(finance.status_code == 200, f"Live finance /ask returns HTTP 200: {finance.text[:300]}")
            f = finance.json()
            print("FINANCE RESPONSE:", f)
            check(f.get("abstained") is False, "Finance question receives a non-abstained answer")
            check(
                "42" in f.get("answer", "") and
                "million" in f.get("answer", "").lower(),
                "Finance answer includes the supported number and unit",
            )
            check(bool(f.get("citations")), "Finance answer includes citations")
            check(
                any(c.get("filename") == "finance-live.txt" for c in f["citations"]),
                "Finance citation identifies the correct source file",
            )
            for citation in f.get("citations", []):
                check(
                    citation.get("source_id") and
                    f"[{citation['source_id']}]" in f.get("answer", ""),
                    "Returned finance citation ID appears in answer",
                )
                check(bool(citation.get("text")), "Finance citation contains source evidence")

            hiring = client.post(
                base + "/ask",
                json={"query": "How many junior Python engineers will the team recruit?",
                      "top_k": 5, "min_similarity": 0.45},
            )
            check(hiring.status_code == 200, f"Live hiring /ask returns HTTP 200: {hiring.text[:300]}")
            h = hiring.json()
            print("HIRING RESPONSE:", h)
            check(h.get("abstained") is False, "Hiring question receives a non-abstained answer")
            check(
                "six" in h.get("answer", "").lower() or "6" in h.get("answer", ""),
                "Hiring answer includes the supported hiring total",
            )
            check(bool(h.get("citations")), "Hiring answer includes citations")
            check(
                any(c.get("filename") == "hiring-live.txt" for c in h["citations"]),
                "Hiring citation identifies the correct source file",
            )
            for citation in h.get("citations", []):
                check(
                    citation.get("source_id") and
                    f"[{citation['source_id']}]" in h.get("answer", ""),
                    "Returned hiring citation ID appears in answer",
                )
                check(bool(citation.get("text")), "Hiring citation contains source evidence")

            unknown = client.post(
                base + "/ask",
                json={
                    "query": "What is the exact serial number of the spacecraft named Zephyr-900?",
                    "top_k": 5,
                    "min_similarity": 1.0,
                },
            )
            check(unknown.status_code == 200, f"Unsupported question /ask returns HTTP 200: {unknown.text[:300]}")
            u = unknown.json()
            print("ABSTENTION RESPONSE:", u)
            check(u.get("abstained") is True, "Unsupported question is explicitly abstained")
            check(u.get("citations") == [], "Unsupported question returns no citations")

        finally:
            client.close()

    results.append("PART 4F LIVE RAG API VERIFICATION: PASS")
    print("PART 4F LIVE RAG API VERIFICATION: PASS")

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
