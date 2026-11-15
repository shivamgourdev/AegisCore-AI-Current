"""AEGISCORE_PART10_HIRING
Phase 10: AI Hiring & Job Application Workflow - Hiring Module.

Handles hiring message input (text and image), structured job information
extraction, and integration with Resume Manager and email draft generation.

No actual email delivery is implemented. Email drafts are for review and
explicit approval only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from aegiscore.document_service import get_resume_attachment
from aegiscore.job_email import generate_job_email
from aegiscore.document_service import DocumentUploadError


MAX_TEXT_LENGTH = 10_000


def _validate_text(value: str, field_name: str) -> str:
    """Validate text input: non-empty string within length limits."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty.")
    if len(value) > MAX_TEXT_LENGTH:
        raise ValueError(
            f"{field_name} must not exceed {MAX_TEXT_LENGTH} characters."
        )
    return value


@dataclass(frozen=True)
class JobAnalysisResult:
    """Structured result of job description analysis."""

    company: str | None
    job_title: str | None
    required_skills: list[str]
    missing_skills: list[str]
    experience_requirements: str | None
    location: str | None
    work_mode: str | None
    salary: str | None
    recruiter_name: str | None
    recruiter_email: str | None
    contact_information: str | None
    application_instructions: str | None
    deadline: str | None
    raw_text: str


def extract_job_information(text: str) -> JobAnalysisResult:
    """Extract structured job information from hiring message text.

    Deterministic extraction using keyword patterns. No LLM is used
    for this extraction to ensure reproducibility and avoid paid APIs.

    Args:
        text: Raw text from hiring message (uploaded image OCR or pasted text).

    Returns:
        JobAnalysisResult with extracted fields. Missing fields are None.

    Raises:
        ValueError: If input is invalid.
    """
    text = _validate_text(text, "text")
    normalized = text.lower()

    # Extract company name - look for common patterns
    company = _extract_company(normalized, text)

    # Extract job title
    job_title = _extract_job_title(normalized, text)

    # Extract skills using existing skill analysis
    from aegiscore.job_analysis import extract_skills

    job_skills = extract_skills(text)

    # Extract missing skills by comparing with empty resume
    missing_skills = job_skills  # All job skills are "missing" without resume

    # Extract experience requirements
    experience_requirements = _extract_experience(text)

    # Extract location
    location = _extract_location(text)

    # Extract work mode
    work_mode = _extract_work_mode(text)

    # Extract salary
    salary = _extract_salary(text)

    # Extract recruiter name
    recruiter_name = _extract_recruiter_name(text)

    # Extract recruiter email
    recruiter_email = _extract_recruiter_email(text)

    # Extract contact information
    contact_information = _extract_contact_info(text)

    # Extract application instructions
    application_instructions = _extract_application_instructions(text)

    # Extract deadline
    deadline = _extract_deadline(text)

    return JobAnalysisResult(
        company=company,
        job_title=job_title,
        required_skills=job_skills,
        missing_skills=missing_skills,
        experience_requirements=experience_requirements,
        location=location,
        work_mode=work_mode,
        salary=salary,
        recruiter_name=recruiter_name,
        recruiter_email=recruiter_email,
        contact_information=contact_information,
        application_instructions=application_instructions,
        deadline=deadline,
        raw_text=text,
    )


def _extract_company(normalized: str, text: str) -> str | None:
    """Extract company name from hiring message."""
    patterns = [
        r"(?:company|company name|company name:|at|@)\s+([A-Z][A-Za-z0-9 &.,'-]{2,50})",
        r"(?:hiring for|join|join us at)\s+([A-Z][A-Za-z0-9 &.,'-]{2,50})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _extract_job_title(normalized: str, text: str) -> str | None:
    """Extract job title from hiring message."""
    patterns = [
        r"(?:position|role|title|job title|position title):\s*([A-Za-z0-9 &.,'-]{2,60})",
        r"(?:for|as a|as an)\s+([A-Z][A-Za-z0-9 &.,'-]{2,60})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _extract_experience(text: str) -> str | None:
    """Extract experience requirements."""
    patterns = [
        r"(\d+\+?\s*years?\s*(?:of\s*)?experience)",
        r"(\d+\+?\s*yrs?\s*exp)",
        r"(\d+-\d+\s*years?\s*experience)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_location(text: str) -> str | None:
    """Extract location from hiring message."""
    patterns = [
        r"(?:location|based in|located in|location:)\s*([A-Za-z0-9 ,.'-]{2,50})",
        r"(?:remote|onsite|on-site|hybrid)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_work_mode(text: str) -> str | None:
    """Extract work mode (remote, onsite, hybrid)."""
    text_lower = text.lower()
    if "remote" in text_lower:
        return "remote"
    if "onsite" in text_lower or "on-site" in text_lower:
        return "onsite"
    if "hybrid" in text_lower:
        return "hybrid"
    return None


def _extract_salary(text: str) -> str | None:
    """Extract salary information."""
    patterns = [
        r"(\$\d[\d,]*(?:\.\d{2})?(?:\s*-\s*\$\d[\d,]*(?:\.\d{2})?)?)",
        r"(\$\d[\d,]*(?:k|K)?\s*(?:-\s*\$\d[\d,]*(?:k|K))?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _extract_recruiter_name(text: str) -> str | None:
    """Extract recruiter name."""
    patterns = [
        r"(?:recruiter|contact|contact person):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"(?:from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _extract_recruiter_email(text: str) -> str | None:
    """Extract recruiter email address."""
    match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    if match:
        return match.group(0).strip()
    return None


def _extract_contact_info(text: str) -> str | None:
    """Extract contact information (phone, website, etc.)."""
    phone_match = re.search(
        r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text
    )
    if phone_match:
        return phone_match.group(0).strip()
    return None


def _extract_application_instructions(text: str) -> str | None:
    """Extract application instructions."""
    patterns = [
        r"(?:apply|application|to apply):\s*([^\n]{10,200})",
        r"(?:send|email|mail)\s+(?:your\s+)?(?:resume|cv)\s+to\s*([^\n]{10,100})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_deadline(text: str) -> str | None:
    """Extract application deadline."""
    patterns = [
        r"(?:deadline|apply by|before)\s*([A-Za-z0-9 ,/-]{5,30})",
        r"(?:by\s+)([A-Za-z]+ \d{1,2}(?:,?\s*\d{4})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def generate_hiring_email_draft(
    candidate_name: str,
    recipient_email: str,
    job_title: str,
    company_name: str,
    resume_summary: str,
    resume_document_id: str,
) -> dict:
    """Generate a professional job application email draft.

    This wraps job_email.generate_job_email with hiring-specific context.
    Never sends email - returns a draft for explicit user approval.

    Args:
        candidate_name: Name of the candidate.
        recipient_email: Recipient email address.
        job_title: Job title being applied for.
        company_name: Company name.
        resume_summary: Summary of candidate's relevant experience.
        resume_document_id: Document ID of the resume attachment.

    Returns:
        Dictionary with draft details including attachment info.

    Raises:
        ValueError: If input validation fails.
        DocumentUploadError: If the resume attachment is not found or invalid.
    """
    from aegiscore.job_email import generate_job_email

    draft = generate_job_email(
        candidate_name=candidate_name,
        recipient_email=recipient_email,
        job_title=job_title,
        company_name=company_name,
        resume_summary=resume_summary,
    )

    # Attach verified resume metadata (SHA-256, filename, document_id)
    metadata, _attachment_path = get_resume_attachment(resume_document_id)
    draft["attachment_document_id"] = metadata["document_id"]
    draft["attachment_filename"] = metadata["filename"]
    draft["attachment_sha256"] = metadata["sha256"]

    return draft


def process_hiring_text(hiring_text: str) -> dict:
    """Process hiring text and extract structured job information.

    This is the main entry point for processing hiring message text.
    It extracts structured job information from the text and returns
    a result dictionary suitable for API responses.

    Args:
        hiring_text: Raw hiring message text.

    Returns:
        Dictionary with extracted job information fields.
    """
    if not hiring_text or not hiring_text.strip():
        return {
            "candidate_name": "",
            "recipient_email": "",
            "job_title": "",
            "company_name": "",
            "resume_summary": "",
            "required_skills": [],
            "missing_skills": [],
            "experience_requirements": None,
            "location": None,
            "work_mode": None,
            "salary": None,
            "recruiter_name": None,
            "recruiter_email": None,
            "contact_information": None,
            "application_instructions": None,
            "deadline": None,
            "raw_text": hiring_text or "",
        }

    result = extract_job_information(hiring_text)
    return {
        "candidate_name": result.recruiter_name or "",
        "recipient_email": result.recruiter_email or "",
        "job_title": result.job_title or "",
        "company_name": result.company or "",
        "resume_summary": result.raw_text[:200] if result.raw_text else "",
        "required_skills": result.required_skills,
        "missing_skills": result.missing_skills,
        "experience_requirements": result.experience_requirements,
        "location": result.location,
        "work_mode": result.work_mode,
        "salary": result.salary,
        "recruiter_name": result.recruiter_name,
        "recruiter_email": result.recruiter_email,
        "contact_information": result.contact_information,
        "application_instructions": result.application_instructions,
        "deadline": result.deadline,
        "raw_text": result.raw_text,
    }


def process_hiring_upload(file_content: bytes, filename: str) -> dict:
    """Process an uploaded hiring document (image) through OCR.

    This is the main entry point for processing uploaded hiring document
    images. It extracts text via OCR and then processes the extracted
    text through the hiring text pipeline.

    Args:
        file_content: Raw image file bytes.
        filename: Original filename of the uploaded file.

    Returns:
        Dictionary with OCR results and extracted job information.

    Raises:
        ValueError: If the file extension is unsupported or OCR processing fails.
    """
    from aegiscore.ocr_service import extract_text_from_image_bytes

    # Validate file extension
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
    if not any(filename.lower().endswith(ext) for ext in image_extensions):
        raise ValueError(
            f"Unsupported file type: {filename}. "
            f"Supported image types: {', '.join(image_extensions)}"
        )

    ocr_result = extract_text_from_image_bytes(file_content)
    extracted_text = ocr_result.get("text", "")
    result = process_hiring_text(extracted_text)
    result["extracted_text"] = extracted_text
    result["ocr_available"] = True
    result["ocr_confidence"] = ocr_result.get("confidence", 0.0)
    return result