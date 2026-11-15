import pytest

from aegiscore.job_analysis import analyze_resume, extract_skills


def test_extracts_skills_case_insensitively():
    assert extract_skills("PYTHON, FastAPI and sql") == [
        "Python", "SQL", "FastAPI"
    ]


def test_does_not_match_skill_inside_larger_word():
    assert extract_skills("pythonista and dockerized") == []


def test_match_percentage_and_missing_skills():
    result = analyze_resume(
        "Python, FastAPI and SQL experience.",
        "We need Python, SQL, Docker and Machine Learning.",
    )
    assert result["matched_skills"] == ["Python", "SQL"]
    assert result["missing_skills"] == ["Machine Learning", "Docker"]
    assert result["match_percentage"] == 50


def test_no_detected_job_skills_returns_zero():
    result = analyze_resume(
        "Python developer",
        "Seeking a curious and motivated candidate.",
    )
    assert result["job_description_skills"] == []
    assert result["match_percentage"] == 0
    assert result["matched_skills"] == []
    assert result["missing_skills"] == []


@pytest.mark.parametrize(
    ("resume", "job"),
    [
        ("", "Python required"),
        ("Python required", ""),
        ("   ", "Python required"),
    ],
)
def test_rejects_empty_inputs(resume, job):
    with pytest.raises(ValueError):
        analyze_resume(resume, job)


def test_rejects_non_string_input():
    with pytest.raises(ValueError):
        analyze_resume(None, "Python required")


def test_rejects_oversized_input():
    with pytest.raises(ValueError, match="50000"):
        analyze_resume("x" * 50001, "Python required")


def test_analysis_is_deterministic():
    resume = "Python, SQL, FastAPI"
    job = "Python, Docker, SQL"
    assert analyze_resume(resume, job) == analyze_resume(resume, job)
