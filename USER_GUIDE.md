# AegisCore AI — User Guide

## Overview

AegisCore AI has three integrated sandboxes:

1. **RAG Knowledge Sandbox** — Upload documents and ask questions with source citations
2. **Resume Sandbox** — Upload and manage resume PDFs for job applications
3. **Job Application Sandbox** — Analyze job fit and create email drafts with explicit approval

## Sandbox 1: RAG Knowledge Sandbox

### Upload Documents
1. Click "Choose files" and select PDF, TXT, or MD files (multiple files allowed)
2. Click "Upload Selected"
3. Wait for the status to show "Uploaded N document(s)"
4. Documents appear in the list with filename, type, size, and ID

### Ask Questions
1. Type your question in the "Ask a question" field
2. Select retrieval mode:
   - **Dense (semantic):** Best for conceptual questions
   - **Sparse (keyword):** Best for exact terms and identifiers
   - **Hybrid (dense + sparse):** Best combined results
3. Click "Ask"
4. Read the answer with source citations

### Citations
Each answer includes numbered citations like [S1], [S2] that reference source documents with filenames, page numbers, and text excerpts.

### Abstention
If the system doesn't have enough evidence to answer, it will say so rather than inventing an answer.

### Delete Documents
Click the "Delete" button next to any document to remove it and its associated data.

## Sandbox 2: Resume Sandbox

### Upload Resume
1. Click "Choose file" and select a PDF resume
2. Click "Upload PDF"
3. The resume text is automatically extracted and displayed in the text area
4. The resume is stored with SHA-256 integrity verification

### Use Resume for Job Analysis
The extracted resume text can be used in the Job Analysis sandbox for skill matching.

### Replace Resume
Uploading a new PDF replaces the current resume. Previous resume documents remain in the system.

## Sandbox 3: Job Application Sandbox

### Step 1: Job Analysis
1. Paste resume text (auto-populated from Resume sandbox)
2. Paste job description
3. Click "Analyze skill match"
4. View matched skills, missing skills, and match percentage

The percentage measures detected skill overlap. It is **not** a prediction of hiring success.

### Step 2: Generate Email Draft
1. Fill in candidate name, recruiter email, job title, company, and resume summary
2. Click "Generate and save draft"
3. The draft is saved with the resume attached (SHA-256 verified)

### Step 3: Review and Edit
1. Edit recipient, subject, and body as needed
2. Click "Save Changes" when done editing

### Step 4: Approve
1. Review all fields and the attachment
2. Check the approval checkbox: "I have reviewed and explicitly approve this exact recipient, email content and resume attachment."
3. Click "Approve this draft"

**Important:** Approval records your approval only. No email is sent. Actual email delivery is not implemented.

## Supported File Formats

| Format | Extension | MIME Type | Max Size |
|--------|-----------|-----------|----------|
| PDF | .pdf | application/pdf | 10 MB |
| Text | .txt | text/plain | 10 MB |
| Markdown | .md | text/markdown | 10 MB |

## Known Limitations

- No OCR for scanned/image-only PDFs
- No cross-encoder reranking (hybrid RRF fusion used)
- No actual email delivery
- No Docker/Kubernetes configuration
