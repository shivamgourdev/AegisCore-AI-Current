"""Generate professional job-application email drafts without sending email."""

import re


MAX_FIELD_LENGTH = 5000


def _clean_field(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    value = value.strip()

    if not value:
        raise ValueError(f"{field_name} must not be empty.")

    if len(value) > MAX_FIELD_LENGTH:
        raise ValueError(
            f"{field_name} must not exceed {MAX_FIELD_LENGTH} characters."
        )

    return value


def _safe_subject(value: str) -> str:
    """Prevent control characters and multiline email subjects."""
    if "\r" in value or "\n" in value:
        raise ValueError("Subject must be a single line.")

    return value


def generate_job_email(
    candidate_name: str,
    recipient_email: str,
    job_title: str,
    company_name: str,
    resume_summary: str,
) -> dict:
    """Create a reviewable draft; this function never sends email."""
    candidate_name = _clean_field(candidate_name, "candidate_name")
    recipient_email = _clean_field(recipient_email, "recipient_email")
    job_title = _clean_field(job_title, "job_title")
    company_name = _clean_field(company_name, "company_name")
    resume_summary = _clean_field(resume_summary, "resume_summary")

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", recipient_email):
        raise ValueError("recipient_email must be a valid email address.")

    if any(char in candidate_name for char in "\r\n"):
        raise ValueError("candidate_name must be a single line.")

    if any(char in job_title for char in "\r\n"):
        raise ValueError("job_title must be a single line.")

    if any(char in company_name for char in "\r\n"):
        raise ValueError("company_name must be a single line.")

    subject = _safe_subject(
        f"Application for {job_title} - {candidate_name}"
    )

    body = (
        f"Dear Hiring Team at {company_name},\n\n"
        f"I am writing to express my interest in the {job_title} position "
        f"at {company_name}.\n\n"
        f"My relevant background includes: {resume_summary}\n\n"
        "I would appreciate the opportunity to discuss how my skills and "
        "experience align with your team's requirements. I have attached "
        "my resume for your review.\n\n"
        "Thank you for your time and consideration.\n\n"
        f"Best regards,\n{candidate_name}"
    )

    return {
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
        "attachment_required": True,
        "requires_user_approval": True,
        "sent": False,
    }
