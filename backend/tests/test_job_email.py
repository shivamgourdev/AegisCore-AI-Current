import pytest
from aegiscore.job_email import generate_job_email


def valid_input(**overrides):
    data = {
        "candidate_name": "Shivam Gour",
        "recipient_email": "hr@example.com",
        "job_title": "AI/ML Intern",
        "company_name": "Example Technologies",
        "resume_summary": "Python, FastAPI and RAG projects",
    }
    data.update(overrides)
    return data


def test_generates_reviewable_email_without_sending():
    draft = generate_job_email(**valid_input())
    assert draft["requires_user_approval"] is True
    assert draft["sent"] is False
    assert draft["attachment_required"] is True
    assert draft["recipient_email"] == "hr@example.com"


@pytest.mark.parametrize(
    "email",
    ["invalid", "hr@", "@example.com", "hr example.com"],
)
def test_rejects_invalid_recipient(email):
    with pytest.raises(ValueError):
        generate_job_email(**valid_input(recipient_email=email))


@pytest.mark.parametrize(
    "field",
    ["candidate_name", "job_title", "company_name"],
)
def test_rejects_newline_in_single_line_fields(field):
    with pytest.raises(ValueError):
        generate_job_email(**valid_input(**{field: "Valid\nBcc: attacker@example.com"}))


def test_rejects_empty_required_field():
    with pytest.raises(ValueError):
        generate_job_email(**valid_input(company_name="  "))


def test_rejects_oversized_field():
    with pytest.raises(ValueError, match="5000"):
        generate_job_email(**valid_input(resume_summary="x" * 5001))
