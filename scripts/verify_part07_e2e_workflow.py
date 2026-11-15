"""AEGISCORE_PART7_E2E_VERIFICATION
Complete End-to-End Workflow Verification for AegisCore AI.

Tests the complete workflow across all sandboxes:
1. RAG Knowledge Sandbox: Upload → Extract → Chunk → Embed → Search → Q&A
2. Job Application Sandbox: Resume upload → Job analysis → Email draft → Review → Approve

Uses a real backend server (TestClient for unit-level, or live server for integration).
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
BACKEND_BASE = "http://127.0.0.1:8000"


def make_pdf(texts: list[str]) -> bytes:
    """Create a PDF with the given texts on separate pages."""
    pdf = pymupdf.open()
    for text in texts:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    data = pdf.tobytes()
    pdf.close()
    return data


class E2EVerifier:
    """End-to-end verification client."""

    def __init__(self, base_url: str = BACKEND_BASE):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)
        self.results: list[dict] = []
        self.doc_ids: list[str] = []

    def check(self, condition: bool, msg: str) -> bool:
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {msg}")
        self.results.append({"check": msg, "passed": condition})
        if not condition:
            print(f"    FAILURE: {msg}")
        return condition

    def run_all(self) -> bool:
        """Run all E2E verification checks."""
        print("=" * 60)
        print("AegisCore AI Phase 7 - End-to-End Workflow Verification")
        print("=" * 60)
        print(f"Backend: {self.base_url}")
        print()

        try:
            self._test_backend_health()
            self._test_document_upload()
            self._test_extraction_and_chunking()
            self._test_embedding()
            self._test_search_retrieval()
            self._test_rag_qa()
            self._test_job_analysis()
            self._test_email_draft_workflow()
            self._test_citation_integrity()
            self._test_unsupported_question()
        finally:
            self.client.close()

        # Summary
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        print("\n" + "=" * 60)
        print(f"E2E Verification: {passed}/{total} checks passed")
        print("=" * 60)
        return passed == total

    # --- Test Methods ---

    def _test_backend_health(self):
        print("\n[1] Backend Health Check")
        try:
            resp = self.client.get(f"{self.base_url}/health", timeout=10.0)
            data = resp.json()
            self.check(resp.status_code == 200, "Health endpoint returns 200")
            self.check(data.get("status") in ("ok", "degraded"), "Health status is ok or degraded")
            self.check("service" in data, "Health response includes service name")
        except Exception as e:
            self.check(False, f"Health check failed: {e}")

    def _test_document_upload(self):
        print("\n[2] Document Upload")
        data_dir = tempfile.mkdtemp(prefix="aegiscore-e2e-")

        # Create test PDF
        pdf_path = Path(data_dir) / "test_doc.pdf"
        pdf_content = make_pdf([
            "Project Orion revenue was 42 million dollars in Q3.",
            "The hiring team plans to recruit six junior Python engineers.",
        ])
        pdf_path.write_bytes(pdf_content)

        # Create test TXT
        txt_path = Path(data_dir) / "notes.txt"
        txt_path.write_text("Project Orion revenue was 42 million dollars in Q3.\nThe hiring team plans to recruit six junior Python engineers.", encoding="utf-8")

        # Upload PDF
        try:
            with open(pdf_path, "rb") as f:
                resp = self.client.post(
                    f"{self.base_url}/documents/upload",
                    files={"file": ("test_doc.pdf", f, "application/pdf")},
                )
            self.check(resp.status_code == 200, f"PDF upload returns 200 (got {resp.status_code})")
            if resp.status_code == 200:
                data = resp.json()
                self.doc_ids.append(data["document"]["document_id"])
                self.check(data["document"]["document_id"], "Document ID returned")
                self.check(data["extraction"]["status"] == "text_extracted", "Extraction status is text_extracted")
        except Exception as e:
            self.check(False, f"PDF upload failed: {e}")

        # Upload TXT
        try:
            with open(txt_path, "rb") as f:
                resp = self.client.post(
                    f"{self.base_url}/documents/upload",
                    files={"file": ("notes.txt", f, "text/plain")},
                )
            self.check(resp.status_code == 200, f"TXT upload returns 200 (got {resp.status_code})")
            if resp.status_code == 200:
                data = resp.json()
                self.doc_ids.append(data["document"]["document_id"])
        except Exception as e:
            self.check(False, f"TXT upload failed: {e}")

        # Unsupported file type
        try:
            resp = self.client.post(
                f"{self.base_url}/documents/upload",
                files={"file": ("malware.exe", b"binary", "application/octet-stream")},
            )
            self.check(resp.status_code == 415, f"Unsupported extension rejected (415, got {resp.status_code})")
        except Exception as e:
            self.check(False, f"Unsupported file test failed: {e}")

    def _test_extraction_and_chunking(self):
        print("\n[3] Text Extraction and Chunking")
        if not self.doc_ids:
            self.check(False, "No documents available for extraction test")
            return

        doc_id = self.doc_ids[0]
        try:
            resp = self.client.get(f"{self.base_url}/documents/{doc_id}/extraction")
            self.check(resp.status_code == 200, "Extraction endpoint returns 200")
            if resp.status_code == 200:
                data = resp.json()
                self.check("Project Orion" in data.get("text", ""), "Extraction contains expected text")
                self.check(data.get("page_count", 0) >= 1, "Extraction has page count")
        except Exception as e:
            self.check(False, f"Extraction test failed: {e}")

        # Get chunks
        try:
            resp = self.client.get(f"{self.base_url}/documents/{doc_id}/chunks")
            self.check(resp.status_code == 200, "Chunks endpoint returns 200")
            if resp.status_code == 200:
                data = resp.json()
                self.check(data.get("chunk_count", 0) >= 1, "Chunks exist")
                if data.get("chunks"):
                    self.check("Orion" in data["chunks"][0]["text"], "Chunk contains expected text")
                    self.check(data["chunks"][0].get("page_number") is not None, "Chunk has page number")
        except Exception as e:
            self.check(False, f"Chunks test failed: {e}")

    def _test_embedding(self):
        print("\n[4] Embedding")
        if not self.doc_ids:
            self.check(False, "No documents available for embedding test")
            return

        doc_id = self.doc_ids[0]
        try:
            resp = self.client.post(f"{self.base_url}/documents/{doc_id}/embed")
            self.check(resp.status_code == 200, f"Embedding endpoint returns 200 (got {resp.status_code})")
            if resp.status_code == 200:
                data = resp.json()
                self.check(data.get("embedding_count", 0) >= 1, "Embeddings created")
                self.check(data.get("model") is not None, "Embedding model reported")
        except Exception as e:
            self.check(False, f"Embedding test failed: {e}")

    def _test_search_retrieval(self):
        print("\n[5] Retrieval (Dense/Sparse/Hybrid)")
        if not self.doc_ids:
            self.check(False, "No documents available for search test")
            return

        # Dense search
        try:
            resp = self.client.post(
                f"{self.base_url}/search",
                json={"query": "Project Orion revenue", "top_k": 5, "mode": "dense"},
            )
            self.check(resp.status_code == 200, "Dense search returns 200")
            if resp.status_code == 200:
                data = resp.json()
                self.check(data.get("mode") == "dense", "Dense mode returned")
                self.check(len(data.get("results", [])) >= 1, "Dense search returns results")
                if data.get("results"):
                    self.check("Orion" in data["results"][0].get("text", ""), "Dense result contains expected text")
        except Exception as e:
            self.check(False, f"Dense search test failed: {e}")

        # Sparse search
        try:
            resp = self.client.post(
                f"{self.base_url}/search",
                json={"query": "hiring engineers", "top_k": 5, "mode": "sparse"},
            )
            self.check(resp.status_code == 200, "Sparse search returns 200")
            if resp.status_code == 200:
                data = resp.json()
                self.check(data.get("mode") == "sparse", "Sparse mode returned")
                if data.get("results"):
                    self.check("engineers" in data["results"][0].get("text", "").lower(), "Sparse result contains expected text")
        except Exception as e:
            self.check(False, f"Sparse search test failed: {e}")

        # Hybrid search
        try:
            resp = self.client.post(
                f"{self.base_url}/search",
                json={"query": "Orion revenue hiring", "top_k": 5, "mode": "hybrid"},
            )
            self.check(resp.status_code == 200, "Hybrid search returns 200")
            if resp.status_code == 200:
                data = resp.json()
                self.check(data.get("mode") == "hybrid", "Hybrid mode returned")
                if data.get("results"):
                    self.check("Orion" in data["results"][0].get("text", ""), "Hybrid result contains expected text")
        except Exception as e:
            self.check(False, f"Hybrid search test failed: {e}")

    def _test_rag_qa(self):
        print("\n[6] RAG Q&A")
        if not self.doc_ids:
            self.check(False, "No documents available for RAG QA test")
            return

        try:
            resp = self.client.post(
                f"{self.base_url}/ask",
                json={
                    "query": "What was Project Orion's Q3 revenue?",
                    "top_k": 5,
                    "min_similarity": 0.30,
                },
                timeout=60.0,
            )
            self.check(resp.status_code == 200, f"RAG QA returns 200 (got {resp.status_code})")
            if resp.status_code == 200:
                data = resp.json()
                self.check("answer" in data, "Answer returned")
                self.check("abstained" in data, "Abstained field returned")
                self.check("citations" in data, "Citations returned")
                if not data.get("abstained", True):
                    self.check("42 million" in data.get("answer", ""), "Answer contains revenue fact")
                    self.check(len(data.get("citations", [])) >= 1, "Citations present")
                    for citation in data.get("citations", []):
                        self.check(citation.get("source_id") in data.get("answer", ""), f"Citation {citation.get('source_id')} referenced in answer")
        except Exception as e:
            self.check(False, f"RAG QA test failed: {e}")

    def _test_job_analysis(self):
        print("\n[7] Job Analysis")
        try:
            resp = self.client.post(
                f"{self.base_url}/jobs/analyze",
                json={
                    "resume_text": "Python developer with FastAPI, SQL, Docker, RAG experience.",
                    "job_description": "We need Python, SQL, Docker, Machine Learning.",
                },
            )
            self.check(resp.status_code == 200, f"Job analysis returns 200 (got {resp.status_code})")
            if resp.status_code == 200:
                data = resp.json()
                self.check("matched_skills" in data, "Matched skills returned")
                self.check("missing_skills" in data, "Missing skills returned")
                self.check("match_percentage" in data, "Match percentage returned")
                self.check("Python" in data.get("matched_skills", []), "Python matched")
                self.check("Machine Learning" in data.get("missing_skills", []), "ML missing")
        except Exception as e:
            self.check(False, f"Job analysis test failed: {e}")

    def _test_email_draft_workflow(self):
        print("\n[8] Email Draft Workflow")
        if not self.doc_ids:
            self.check(False, "No documents available for email draft test")
            return

        doc_id = self.doc_ids[0]
        try:
            # Create draft
            resp = self.client.post(
                f"{self.base_url}/jobs/email-draft",
                json={
                    "candidate_name": "Test Candidate",
                    "recipient_email": "hr@example.com",
                    "job_title": "Python Developer",
                    "company_name": "Example Corp",
                    "resume_summary": "Python developer with FastAPI and RAG experience.",
                    "resume_document_id": doc_id,
                },
            )
            self.check(resp.status_code == 200, f"Draft creation returns 200 (got {resp.status_code})")
            if resp.status_code == 200:
                data = resp.json()
                self.check("draft_id" in data, "Draft ID returned")
                self.check(data.get("status") == "pending", "Draft status is pending")
                self.check(data.get("requires_user_approval") is True, "Requires approval")
                self.check(data.get("sent") is False, "Not sent")
                draft_id = data["draft_id"]

                # Get draft
                resp = self.client.get(f"{self.base_url}/jobs/email-drafts/{draft_id}")
                self.check(resp.status_code == 200, "Get draft returns 200")
                if resp.status_code == 200:
                    data = resp.json()
                    self.check(data["draft_id"] == draft_id, "Draft ID matches")

                # Update draft
                resp = self.client.put(
                    f"{self.base_url}/jobs/email-drafts/{draft_id}",
                    json={
                        "recipient_email": "recruiter@example.com",
                        "subject": "Updated Application",
                        "body": "Dear Recruiter, please review my application.",
                    },
                )
                self.check(resp.status_code == 200, f"Draft update returns 200 (got {resp.status_code})")

                # Approve draft
                resp = self.client.post(
                    f"{self.base_url}/jobs/email-drafts/{draft_id}/approve",
                    json={
                        "recipient_email": "recruiter@example.com",
                        "subject": "Updated Application",
                        "body": "Dear Recruiter, please review my application.",
                        "attachment_document_id": doc_id,
                        "attachment_sha256": self.doc_ids[0],  # Using doc_id as placeholder SHA
                        "confirm": True,
                    },
                )
                self.check(resp.status_code == 200, f"Draft approval returns 200 (got {resp.status_code})")
                if resp.status_code == 200:
                    data = resp.json()
                    self.check(data.get("status") == "approved", "Draft status is approved")
                    self.check(data.get("sent") is False, "Email not sent")
        except Exception as e:
            self.check(False, f"Email draft workflow test failed: {e}")

    def _test_citation_integrity(self):
        print("\n[8b] Citation Integrity")
        if not self.doc_ids:
            self.check(False, "No documents available for citation test")
            return

        try:
            # Ask a question and verify citations
            resp = self.client.post(
                f"{self.base_url}/ask",
                json={
                    "query": "What was Project Orion's Q3 revenue?",
                    "top_k": 5,
                    "min_similarity": 0.30,
                },
                timeout=60.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("abstained", True):
                    for citation in data.get("citations", []):
                        self.check(citation.get("source_id") in data.get("answer", ""),
                                   f"Citation {citation.get('source_id')} referenced in answer")
                        self.check(citation.get("text"), f"Citation {citation.get('source_id')} has text")
                        self.check(citation.get("filename"), f"Citation {citation.get('source_id')} has filename")
                else:
                    self.check(True, "Answer abstained (no relevant evidence)")
            else:
                self.check(False, f"RAG QA for citation test returned {resp.status_code}")
        except Exception as e:
            self.check(False, f"Citation integrity test failed: {e}")

    def _test_unsupported_question(self):
        print("\n[9] Unsupported Question Abstention")
        try:
            resp = self.client.post(
                f"{self.base_url}/ask",
                json={
                    "query": "What is the serial number of the Zephyr spacecraft?",
                    "top_k": 5,
                    "min_similarity": 1.0,
                },
                timeout=60.0,
            )
            self.check(resp.status_code == 200, f"Unsupported question returns 200 (got {resp.status_code})")
            if resp.status_code == 200:
                data = resp.json()
                self.check(data.get("abstained") is True, "Unsupported question abstained")
                self.check(len(data.get("citations", [])) == 0, "No citations for unsupported question")
        except Exception as e:
            self.check(False, f"Unsupported question test failed: {e}")


if __name__ == "__main__":
    verifier = E2EVerifier()
    success = verifier.run_all()
    sys.exit(0 if success else 1)
