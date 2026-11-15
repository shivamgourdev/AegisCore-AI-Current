"""Deterministic resume and job-description skill matching."""

import re

MAX_TEXT_LENGTH = 50_000

# Canonical skill names and their recognized spellings.
SKILL_ALIASES = {
    "Python": ["python"],
    "SQL": ["sql", "structured query language"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning"],
    "NLP": ["nlp", "natural language processing"],
    "Generative AI": ["generative ai", "gen ai", "genai"],
    "RAG": ["rag", "retrieval augmented generation"],
    "LangChain": ["langchain"],
    "LangGraph": ["langgraph"],
    "FastAPI": ["fastapi"],
    "Flask": ["flask"],
    "Django": ["django"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow"],
    "Scikit-learn": ["scikit-learn", "sklearn"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes"],
    "Git": ["git", "github"],
    "REST API": ["rest api", "restful api"],
    "Linux": ["linux"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure", "microsoft azure"],
    "GCP": ["gcp", "google cloud platform"],
    "SQLAlchemy": ["sqlalchemy"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb"],
    "Redis": ["redis"],
    "FAISS": ["faiss"],
    "ChromaDB": ["chromadb", "chroma db"],
    "Streamlit": ["streamlit"],
    "HTML": ["html"],
    "CSS": ["css"],
    "JavaScript": ["javascript"],
    "TypeScript": ["typescript"],
    "Java": ["java"],
    "C++": ["c++"],
    "C#": ["c#"],
    "Communication": ["communication", "communication skills"],
    "Problem Solving": ["problem solving", "problem-solving"],
}

def _validate_text(value: str, field_name: str) -> str:
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


def extract_skills(text: str) -> list[str]:
    """Return recognized skills in vocabulary order, without duplicates."""
    text = _validate_text(text, "text")
    normalized = text.casefold()
    found = []

    for canonical, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            # Match whole terms, allowing punctuation in names such as C++.
            pattern = r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)"
            if re.search(pattern, normalized):
                found.append(canonical)
                break

    return found


def analyze_resume(resume_text: str, job_description: str) -> dict:
    """Compare recognized skills; this is not a hiring-probability estimate."""
    resume_text = _validate_text(resume_text, "resume_text")
    job_description = _validate_text(job_description, "job_description")

    resume_skills = extract_skills(resume_text)
    job_skills = extract_skills(job_description)

    resume_set = set(resume_skills)
    job_set = set(job_skills)

    matched = [skill for skill in job_skills if skill in resume_set]
    missing = [skill for skill in job_skills if skill not in resume_set]

    percentage = round((len(matched) / len(job_skills)) * 100) if job_skills else 0

    return {
        "resume_skills": resume_skills,
        "job_description_skills": job_skills,
        "matched_skills": matched,
        "missing_skills": missing,
        "match_percentage": percentage,
        "match_basis": "matched detected job-description skills / all detected job-description skills",
        "interpretation": (
            "Text-based skill overlap only; this percentage does not predict hiring success."
        ),
    }

