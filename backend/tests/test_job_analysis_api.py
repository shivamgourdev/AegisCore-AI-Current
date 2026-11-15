import pytest
from fastapi.testclient import TestClient
from aegiscore.main import app

client = TestClient(app)


def test_job_analysis_api_returns_skill_matches():
    response = client.post(
        "/jobs/analyze",
        json={
            "resume_text": "Python, FastAPI and SQL experience.",
            "job_description": (
                "We need Python, SQL, Docker and Machine Learning."
            ),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["matched_skills"] == ["Python", "SQL"]
    assert set(data["missing_skills"]) == {
        "Docker", "Machine Learning"
    }
    assert data["match_percentage"] == 50
    assert "does not predict hiring success" in data["interpretation"]


@pytest.mark.parametrize(
    "payload",
    [
        {"resume_text": "", "job_description": "Python required"},
        {"resume_text": "   ", "job_description": "Python required"},
        {"resume_text": "Python required", "job_description": ""},
        {
            "resume_text": "x" * 50001,
            "job_description": "Python required",
        },
    ],
)
def test_job_analysis_api_rejects_invalid_input(payload):
    response = client.post("/jobs/analyze", json=payload)
    assert response.status_code == 422


def test_job_analysis_api_rejects_missing_fields():
    response = client.post(
        "/jobs/analyze",
        json={"resume_text": "Python developer"},
    )
    assert response.status_code == 422
