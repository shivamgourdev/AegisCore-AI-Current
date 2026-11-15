"""Stage 2 Phase 6: Job Analysis Sandbox - verification.
Tests:
- Saved resume selection
- Job description input
- Skill extraction
- Matched skills
- Missing skills
- Deterministic score
- Invalid and empty job description
- Missing resume
- Repeated identical input producing reproducible results
"""
import sys
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND_BASE = "http://127.0.0.1:8000"


def main():
    results = []
    client = None

    def check(cond, msg):
        status = "PASS" if cond else "FAIL"
        line = f"[{status}] {msg}"
        results.append(line)
        print(line)
        if not cond:
            raise AssertionError(msg)

    try:
        client = httpx.Client(timeout=10.0)
        check(client.get(BACKEND_BASE + "/health").status_code == 200, "Backend health OK")

        # Create a resume document first
        import pymupdf
        data_dir = tempfile.mkdtemp(prefix="aegiscore-job-")
        resume_path = Path(data_dir) / "resume.pdf"
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text((72, 72), "Shivam Gour\nPython Developer\nSkills: Python, FastAPI, SQL, RAG, Docker\nExperience: Built RAG systems with FastAPI and Ollama.")
        pdf.save(str(resume_path))
        pdf.close()

        with open(resume_path, "rb") as f:
            resume_upload = client.post(
                BACKEND_BASE + "/documents/upload",
                files={"file": ("resume.pdf", f.read(), "application/pdf")},
            )
        check(resume_upload.status_code == 200, f"Resume upload OK: {resume_upload.status_code}")
        resume_doc_id = resume_upload.json()["document"]["document_id"]

        # Get extracted text
        ext = client.get(BACKEND_BASE + f"/documents/{resume_doc_id}/extraction")
        check(ext.status_code == 200, "Extraction OK")
        resume_text = ext.json().get("text", "")
        check(len(resume_text) > 0, "Resume text extracted")

        # === Job Analysis Tests ===

        # 1. Valid analysis
        analysis = client.post(
            BACKEND_BASE + "/jobs/analyze",
            json={
                "resume_text": resume_text,
                "job_description": "We need a Python developer with FastAPI, SQL, Docker, and Machine Learning experience.",
            },
        )
        check(analysis.status_code == 200, f"Job analysis OK: {analysis.status_code}")
        analysis_data = analysis.json()
        check("Python" in analysis_data["matched_skills"], "Python matched")
        check("FastAPI" in analysis_data["matched_skills"], "FastAPI matched")
        check("SQL" in analysis_data["matched_skills"], "SQL matched")
        check("Docker" in analysis_data["matched_skills"], "Docker matched")
        check("Machine Learning" in analysis_data["missing_skills"], "ML missing")
        check(isinstance(analysis_data["match_percentage"], int), "Match percentage is int")
        check(analysis_data["match_percentage"] > 0, "Match percentage > 0")
        check("does not predict" in analysis_data.get("interpretation", "").lower(),
              "Score explicitly stated as not predicting hiring success")

        # 2. Deterministic - same input produces same result
        analysis2 = client.post(
            BACKEND_BASE + "/jobs/analyze",
            json={
                "resume_text": resume_text,
                "job_description": "We need a Python developer with FastAPI, SQL, Docker, and Machine Learning experience.",
            },
        )
        check(analysis2.status_code == 200, "Repeat analysis OK")
        analysis2_data = analysis2.json()
        check(analysis_data["match_percentage"] == analysis2_data["match_percentage"],
              "Deterministic: same input = same score")
        check(analysis_data["matched_skills"] == analysis2_data["matched_skills"],
              "Deterministic: same matched skills")

        # 3. Empty job description
        empty_jd = client.post(
            BACKEND_BASE + "/jobs/analyze",
            json={"resume_text": resume_text, "job_description": ""},
        )
        check(empty_jd.status_code == 422, f"Empty job description rejected: {empty_jd.status_code}")

        # 4. Empty resume text
        empty_resume = client.post(
            BACKEND_BASE + "/jobs/analyze",
            json={"resume_text": "", "job_description": "Python developer needed"},
        )
        check(empty_resume.status_code == 422, f"Empty resume text rejected: {empty_resume.status_code}")

        # 5. No matching skills
        no_match = client.post(
            BACKEND_BASE + "/jobs/analyze",
            json={
                "resume_text": "Experience with cooking and baking.",
                "job_description": "We need a Python developer with FastAPI experience.",
            },
        )
        check(no_match.status_code == 200, "No-match analysis OK")
        no_match_data = no_match.json()
        check(no_match_data["match_percentage"] == 0, "Zero match when no skills overlap")
        check(len(no_match_data["matched_skills"]) == 0, "No matched skills")

        # 6. All skills match
        all_match = client.post(
            BACKEND_BASE + "/jobs/analyze",
            json={
                "resume_text": "Python, FastAPI, SQL, Docker experience.",
                "job_description": "We need Python, FastAPI, SQL, Docker.",
            },
        )
        check(all_match.status_code == 200, "All-match analysis OK")
        all_match_data = all_match.json()
        check(all_match_data["match_percentage"] == 100, "100% match when all skills overlap")
        check(len(all_match_data["missing_skills"]) == 0, "No missing skills")

        # 7. Oversized input
        oversized = client.post(
            BACKEND_BASE + "/jobs/analyze",
            json={
                "resume_text": "x" * 50001,
                "job_description": "Python developer needed",
            },
        )
        check(oversized.status_code == 422, f"Oversized resume rejected: {oversized.status_code}")

        # 8. Score is not a hiring probability
        check("probability" not in analysis_data.get("interpretation", "").lower(),
              "Interpretation does not claim hiring probability")
        check("overlap" in analysis_data.get("match_basis", "").lower() or "detected" in analysis_data.get("match_basis", "").lower(),
              "Match basis describes skill overlap")

        results.append("\n=== JOB ANALYSIS SANDBOX VERIFICATION: ALL CHECKS PASSED ===")
        print("\n=== JOB ANALYSIS SANDBOX VERIFICATION: ALL CHECKS PASSED ===")

    except Exception as exc:
        results.append(f"\n=== VERIFICATION FAILED: {type(exc).__name__}: {exc} ===")
        print(f"\n=== VERIFICATION FAILED: {type(exc).__name__}: {exc} ===")
        raise
    finally:
        if client is not None:
            client.close()
        import shutil
        try:
            shutil.rmtree(data_dir, ignore_errors=True)
        except Exception:
            pass

    evidence_path = ROOT / "evidence" / "part-09-job-analysis-verification.txt"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("\n".join(results) + "\n", encoding="utf-8")
    print(f"\nEvidence written to: {evidence_path}")


if __name__ == "__main__":
    main()
