"""AEGISCORE_PART4_RESTART
Persistence and restart recovery tests using a real Uvicorn subprocess.

Verifies that documents, chunks, metadata, and embeddings survive
a complete server stop and restart using the same data directory.
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
import pytest

ROOT = Path(__file__).resolve().parents[2]


def _find_free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_server(data_dir, port, log_handle):
    env = os.environ.copy()
    env["AEGISCORE_DATA_DIR"] = str(data_dir)
    env["PYTHONPATH"] = str(ROOT / "backend" / "app")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "aegiscore.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT / "backend" / "app"),
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


class TestRestartPersistence:
    def test_documents_chunks_embeddings_survive_restart(self, tmp_path):
        data_dir = tmp_path / "aegiscore-data"
        data_dir.mkdir(parents=True, exist_ok=True)
        port = _find_free_port()
        log_path = tmp_path / "uvicorn.log"
        log_handle = open(log_path, "w", encoding="utf-8")

        server = None
        client = None
        try:
            # Start first server instance
            server = _start_server(data_dir, port, log_handle)
            base = f"http://127.0.0.1:{port}"
            client = _wait_for_health(base)

            # Upload two documents
            doc_a = client.post(
                base + "/documents/upload",
                files={"file": ("orion.txt",
                                b"Project Orion revenue was 42 million dollars in Q3.",
                                "text/plain")},
            )
            assert doc_a.status_code == 200, doc_a.text
            doc_a_id = doc_a.json()["document"]["document_id"]

            doc_b = client.post(
                base + "/documents/upload",
                files={"file": ("hiring.txt",
                                b"The hiring team plans to recruit six junior Python engineers.",
                                "text/plain")},
            )
            assert doc_b.status_code == 200, doc_b.text
            doc_b_id = doc_b.json()["document"]["document_id"]

            # Embed both documents
            embed_a = client.post(base + f"/documents/{doc_a_id}/embed")
            assert embed_a.status_code == 200, embed_a.text
            assert embed_a.json()["embedding_count"] > 0

            embed_b = client.post(base + f"/documents/{doc_b_id}/embed")
            assert embed_b.status_code == 200, embed_b.text
            assert embed_b.json()["embedding_count"] > 0

            # Verify chunks and embeddings before restart
            chunks_a = client.get(base + f"/documents/{doc_a_id}/chunks")
            assert chunks_a.status_code == 200
            assert chunks_a.json()["chunk_count"] >= 1

            emb_a = client.get(base + f"/documents/{doc_a_id}/embeddings")
            assert emb_a.status_code == 200
            assert emb_a.json()["embedding_count"] >= 1

            # List documents
            docs_list = client.get(base + "/documents")
            assert docs_list.status_code == 200
            doc_ids_before = {d["document_id"] for d in docs_list.json()["documents"]}
            assert doc_a_id in doc_ids_before
            assert doc_b_id in doc_ids_before

            client.close()
            client = None

            # Stop the server completely
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            assert server.poll() is not None, "Server did not stop"
            server = None

            # Start a fresh server with the same data directory
            log_handle2 = open(tmp_path / "uvicorn2.log", "w", encoding="utf-8")
            server2 = _start_server(data_dir, port, log_handle2)
            try:
                client2 = _wait_for_health(base)

                # Verify documents persist
                docs_list2 = client2.get(base + "/documents")
                assert docs_list2.status_code == 200
                doc_ids_after = {d["document_id"] for d in docs_list2.json()["documents"]}
                assert doc_a_id in doc_ids_after, f"Document {doc_a_id} lost after restart"
                assert doc_b_id in doc_ids_after, f"Document {doc_b_id} lost after restart"

                # Verify chunks persist
                chunks_a2 = client2.get(base + f"/documents/{doc_a_id}/chunks")
                assert chunks_a2.status_code == 200
                assert chunks_a2.json()["chunk_count"] >= 1, "Chunks lost after restart"

                # Verify embeddings persist
                emb_a2 = client2.get(base + f"/documents/{doc_a_id}/embeddings")
                assert emb_a2.status_code == 200
                assert emb_a2.json()["embedding_count"] >= 1, "Embeddings lost after restart"

                # Verify extraction persists
                ext_a2 = client2.get(base + f"/documents/{doc_a_id}/extraction")
                assert ext_a2.status_code == 200
                assert "Project Orion revenue" in ext_a2.json()["text"], "Extraction text lost after restart"

                # Perform a new retrieval after restart
                search_after = client2.post(
                    base + "/search",
                    json={"query": "Project Orion revenue", "top_k": 5},
                )
                assert search_after.status_code == 200
                results = search_after.json()["results"]
                assert len(results) >= 1, "No search results after restart"
                assert any("Orion" in r.get("text", "") for r in results), "Expected content not found after restart"

                # Perform a new QA after restart (live Ollama)
                ask_after = client2.post(
                    base + "/ask",
                    json={"query": "What was Project Orion's revenue in Q3?", "top_k": 5, "min_similarity": 0.4},
                )
                assert ask_after.status_code == 200, ask_after.text
                ask_data = ask_after.json()
                assert ask_data["abstained"] is False, ask_data
                assert any(c["filename"] == "orion.txt" for c in ask_data["citations"]), ask_data

                # Verify citation IDs still reference correct passages
                for citation in ask_data["citations"]:
                    assert citation["source_id"] in ask_data["answer"], citation
                    assert citation["text"], citation

                client2.close()
            finally:
                if server2 is not None and server2.poll() is None:
                    server2.terminate()
                    try:
                        server2.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        server2.kill()
                        server2.wait(timeout=5)
                log_handle2.close()

        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            if server is not None and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
            log_handle.close()

    def test_interrupted_processing_safe_recovery(self, tmp_path):
        """Test that a document with failed extraction doesn't block recovery."""
        data_dir = tmp_path / "aegiscore-interrupted"
        data_dir.mkdir(parents=True, exist_ok=True)
        port = _find_free_port()
        log_path = tmp_path / "uvicorn_interrupted.log"
        log_handle = open(log_path, "w", encoding="utf-8")

        server = None
        client = None
        try:
            server = _start_server(data_dir, port, log_handle)
            base = f"http://127.0.0.1:{port}"
            client = _wait_for_health(base)

            # Upload a corrupt PDF (extraction will fail)
            corrupt = client.post(
                base + "/documents/upload",
                files={"file": ("broken.pdf", b"%PDF-broken-content", "application/pdf")},
            )
            assert corrupt.status_code == 200, corrupt.text
            corrupt_id = corrupt.json()["document"]["document_id"]
            assert corrupt.json()["extraction"]["status"] == "extraction_failed"

            # Upload a valid document alongside
            valid = client.post(
                base + "/documents/upload",
                files={"file": ("valid.txt", b"Valid document content for recovery testing.", "text/plain")},
            )
            assert valid.status_code == 200, valid.text
            valid_id = valid.json()["document"]["document_id"]

            embed_valid = client.post(base + f"/documents/{valid_id}/embed")
            assert embed_valid.status_code == 200

            client.close()
            client = None

            # Stop and restart
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            server = None

            log_handle2 = open(tmp_path / "uvicorn_interrupted2.log", "w", encoding="utf-8")
            server2 = _start_server(data_dir, port, log_handle2)
            try:
                client2 = _wait_for_health(base)

                # Both documents should still be registered
                docs_list = client2.get(base + "/documents")
                doc_ids = {d["document_id"] for d in docs_list.json()["documents"]}
                assert corrupt_id in doc_ids
                assert valid_id in doc_ids

                # Corrupt document still shows extraction failure
                ext_corrupt = client2.get(base + f"/documents/{corrupt_id}/extraction")
                assert ext_corrupt.status_code == 200
                assert ext_corrupt.json()["status"] == "extraction_failed"

                # Valid document still has embeddings
                emb_valid = client2.get(base + f"/documents/{valid_id}/embeddings")
                assert emb_valid.status_code == 200
                assert emb_valid.json()["embedding_count"] >= 1

                # Service is healthy after restart
                health = client2.get(base + "/health")
                assert health.status_code == 200

                client2.close()
            finally:
                if server2 is not None and server2.poll() is None:
                    server2.terminate()
                    try:
                        server2.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        server2.kill()
                        server2.wait(timeout=5)
                log_handle2.close()

        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            if server is not None and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
            log_handle.close()
