"""End-to-end verification of all three sandboxes."""
import sys
sys.path.insert(0, 'backend/app')
from fastapi.testclient import TestClient
from aegiscore.main import app
import pymupdf

client = TestClient(app)

# ===== SANDBOX 1: RAG Knowledge Sandbox ============
print("=== SANDBOX 1: RAG KNOWLEDGE ===")
pdf = pymupdf.open()
page = pdf.new_page()
page.insert_text((72, 72), "Project Orion revenue was 42 million dollars in Q3.")
pdf_bytes = pdf.tobytes()
pdf.close()

resp = client.post("/documents/upload", files={"file": ("orion.pdf", pdf_bytes, "application/pdf")})
assert resp.status_code == 200, f"Upload failed: {resp.status_code}"
doc_id = resp.json()["document"]["document_id"]
print(f"  Upload OK - document_id: {doc_id}")

resp = client.post("/ask", json={"query": "What was Project Orion's Q3 revenue?", "top_k": 5, "min_similarity": 0.30})
assert resp.status_code == 200
data = resp.json()
print(f"  RAG QA answer: {data['answer'][:80]}...")
assert not data["abstained"], "Should not abstain"
assert "42 million" in data["answer"]
print(f"  Citation in answer: {'S1' in data['answer'] or any(c.get('source_id') in data['answer'] for c in data.get('citations', []))}")

# ===== SANDBOX 2: Resume Manager Sandbox ============
print()
print("=== SANDBOX 2: RESUME MANAGER ===")
pdf = pymupdf.open()
page = pdf.new_page()
page.insert_text((72, 72), "Shivam Gour\nPython Developer\nSkills: Python, FastAPI, SQL, RAG, Docker")
pdf_bytes = pdf.tobytes()
pdf.close()

resp = client.post("/documents/upload", files={"file": ("resume.pdf", pdf_bytes, "application/pdf")})
assert resp.status_code == 200, f"Upload failed: {resp.status_code}"
doc_id = resp.json()["document"]["document_id"]
print(f"  Resume uploaded - doc_id: {doc_id}")

resp = client.get(f"/documents/{doc_id}/chunks")
assert resp.status_code == 200
chunks = resp.json()["chunks"]
print(f"  Chunks: {len(chunks)}")

# ===== SANDBOX 3: Job Application Sandbox ============
print()
print("=== SANDBOX 3: JOB APPLICATION ===")
resp = client.post("/jobs/analyze", json={
    "resume_text": "Python Developer\nSkills: Python, FastAPI, SQL, RAG, Docker",
    "job_description": "We need Python, SQL, Docker, Machine Learning."
})
assert resp.status_code == 200
data = resp.json()
print(f"  Job analysis: {data['match_percentage']}% match")
print(f"  Matched: {data['matched_skills']}")
print(f"  Missing: {data['missing_skills']}")

resp = client.post("/jobs/email-draft", json={
    "candidate_name": "Shivam Gour",
    "recipient_email": "hr@example.com",
    "job_title": "Python Developer",
    "company_name": "TechCorp",
    "resume_summary": "Python developer with FastAPI and RAG experience",
    "resume_document_id": doc_id
})
assert response.status_code == 200
draft = response.json()
print(f"  Draft created: {draft['draft_id'][:8]}... status={draft['status']}")
print(f"  Attachment filename: {draft['attachment_filename']}")
print(f"  SHA-256: {draft['attachment_sha256'][:16]}...")
print(f"  Sent: {draft['sent']}")
print(f"  Requires approval: {draft['requires_user_approval']}")

print()
print("ALL THREE SANDBOXES VERIFIED END-TO-END")