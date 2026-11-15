"""Real end-to-end verification of Ollama embeddings and semantic search."""
import os
import sys
import tempfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "backend" / "app"
BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"

for import_root in (APP_ROOT, BACKEND_ROOT):
    if import_root.is_dir() and str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

with tempfile.TemporaryDirectory(prefix="aegiscore-part4d-") as data_dir:
    os.environ["AEGISCORE_DATA_DIR"] = data_dir
    from fastapi.testclient import TestClient
    from aegiscore.main import app

    with TestClient(app) as client:
        upload = client.post(
            "/documents/upload",
            files={"file": (
                "live_revenue_report.txt",
                b"Revenue increased 18 percent this quarter. "
                b"Operating costs remained stable.",
                "text/plain",
            )},
        )
        assert upload.status_code == 200, upload.text
        document_id = upload.json()["document"]["document_id"]

        embedded = client.post(f"/documents/{document_id}/embed")
        assert embedded.status_code == 200, embedded.text
        embed_data = embedded.json()
        assert embed_data["embedding_count"] > 0, embed_data
        assert embed_data["dimension"] == 768, embed_data
        assert embed_data["model"] == "nomic-embed-text:latest", embed_data
        print("PASS: Real Ollama embeddings:", embed_data["embedding_count"],
              "vector(s),", embed_data["dimension"], "dimensions.")

        metadata = client.get(f"/documents/{document_id}/embeddings")
        assert metadata.status_code == 200, metadata.text
        stored = metadata.json()
        assert stored["embedding_count"] == embed_data["embedding_count"], stored
        assert all(item["dimension"] == 768 for item in stored["embeddings"])
        assert all(abs(item["vector_norm"] - 1.0) < 1e-5
                   for item in stored["embeddings"])
        print("PASS: Persisted vectors and normalized vector norms verified.")

        search = client.post("/search", json={
            "query": "What happened to revenue this quarter?", "top_k": 3
        })
        assert search.status_code == 200, search.text
        results = search.json()["results"]
        assert results, "Semantic search returned no results."
        assert results[0]["filename"] == "live_revenue_report.txt", results
        assert "Revenue increased" in results[0]["text"], results
        print("PASS: Semantic search returned expected source:",
              results[0]["filename"], "| page:", results[0]["page_number"],
              "| similarity:", round(results[0]["similarity"], 5))

print("PART 4D REAL OLLAMA END-TO-END RESULT: PASS")
