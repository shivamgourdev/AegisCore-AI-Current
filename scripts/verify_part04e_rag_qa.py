"""Real multi-document RAG integration using the local Ollama models."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for root in (ROOT / "backend" / "app", ROOT / "backend"):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

with tempfile.TemporaryDirectory(prefix="aegiscore-part4e-") as data_dir:
    os.environ["AEGISCORE_DATA_DIR"] = data_dir

    from fastapi.testclient import TestClient
    from aegiscore.main import app

    with TestClient(app) as client:
        docs = [
            (
                "finance.txt",
                b"Project Orion revenue was 42 million dollars in Q3. "
                b"The finance team confirmed this figure on October 2.",
            ),
            (
                "hiring.txt",
                b"The hiring team plans to recruit six junior Python engineers in November.",
            ),
        ]

        ids = {}
        for filename, content in docs:
            response = client.post(
                "/documents/upload",
                files={"file": (filename, content, "text/plain")},
            )
            assert response.status_code == 200, response.text
            ids[filename] = response.json()["document"]["document_id"]

            embedded = client.post(f"/documents/{ids[filename]}/embed")
            assert embedded.status_code == 200, embedded.text
            assert embedded.json()["embedding_count"] > 0
            print("PASS: Embedded document:", filename)

        # Prove retrieval can see both uploaded documents in the same corpus.
        search = client.post(
            "/search",
            json={"query": "Project Orion Q3 revenue", "top_k": 10},
        )
        assert search.status_code == 200, search.text
        found = {item["filename"] for item in search.json()["results"]}
        assert {"finance.txt", "hiring.txt"}.issubset(found), found
        print("PASS: Multi-document corpus retrieval returned both sources.")

        finance = client.post(
            "/ask",
            json={
                "query": "What was Project Orion's revenue in Q3?",
                "top_k": 5,
                "min_similarity": 0.40,
            },
        )
        assert finance.status_code == 200, finance.text
        finance_data = finance.json()
        assert finance_data["abstained"] is False, finance_data
        assert finance_data["answer"].strip(), finance_data
        assert any(c["filename"] == "finance.txt" for c in finance_data["citations"]), finance_data
        finance_answer = finance_data["answer"].lower()
        assert "42 million dollars" in finance_answer, finance_data
        assert "project orion" in finance_answer, finance_data
        assert "extrude" not in finance_answer, finance_data
        print("PASS: Finance answer has expected fact, readable wording, and source citation.")
        print("ANSWER:", finance_data["answer"])

        hiring = client.post(
            "/ask",
            json={
                "query": "How many junior Python engineers are planned for recruitment?",
                "top_k": 5,
                "min_similarity": 0.40,
            },
        )
        assert hiring.status_code == 200, hiring.text
        hiring_data = hiring.json()
        assert hiring_data["abstained"] is False, hiring_data
        assert any(c["filename"] == "hiring.txt" for c in hiring_data["citations"]), hiring_data
        hiring_answer = hiring_data["answer"].lower()
        assert "six" in hiring_answer or "6" in hiring_answer, hiring_data
        assert "junior python engineers" in hiring_answer, hiring_data
        print("PASS: Hiring answer has expected fact, readable wording, and source citation.")
        print("ANSWER:", hiring_data["answer"])

        # A threshold of 1.0 should reject a normal, non-identical query match.
        abstention = client.post(
            "/ask",
            json={
                "query": "Give me the lunar tax identification number for Zyxwvu.",
                "top_k": 5,
                "min_similarity": 1.0,
            },
        )
        assert abstention.status_code == 200, abstention.text
        abstention_data = abstention.json()
        assert abstention_data["abstained"] is True, abstention_data
        assert abstention_data["citations"] == [], abstention_data
        print("PASS: Insufficient evidence caused an abstention with no citations.")

print("PART 4E REAL MULTI-DOCUMENT RAG RESULT: PASS")
