"""Persistent storage for reviewable job-application email drafts."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from aegiscore.document_service import get_data_dir


def _connect():
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(data_dir / "aegiscore.db"),
        timeout=10,
    )
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS job_email_drafts (
            draft_id TEXT PRIMARY KEY,
            recipient_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            attachment_document_id TEXT NOT NULL,
            attachment_filename TEXT NOT NULL,
            attachment_sha256 TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('pending', 'approved', 'rejected', 'sent')
            ),
            created_at TEXT NOT NULL,
            approved_at TEXT,
            sent_at TEXT
        )
        """
    )
    connection.commit()
    return connection


def create_draft(draft: dict) -> dict:
    """Persist a new draft as pending; never sends email."""
    required = (
        "recipient_email",
        "subject",
        "body",
        "attachment_document_id",
        "attachment_filename",
        "attachment_sha256",
    )
    for key in required:
        if not isinstance(draft.get(key), str) or not draft[key].strip():
            raise ValueError(f"Missing or invalid draft field: {key}")

    draft_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO job_email_drafts (
                draft_id, recipient_email, subject, body,
                attachment_document_id, attachment_filename,
                attachment_sha256, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                draft_id,
                draft["recipient_email"],
                draft["subject"],
                draft["body"],
                draft["attachment_document_id"],
                draft["attachment_filename"],
                draft["attachment_sha256"],
                created_at,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    return get_draft(draft_id)


def get_draft(draft_id: str) -> dict | None:
    """Retrieve a stored draft without exposing internal database details."""
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT * FROM job_email_drafts WHERE draft_id = ?",
            (draft_id,),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        connection.close()


def approve_draft(
    draft_id: str,
    reviewed: dict,
) -> dict | None:
    """Approve only if the exact saved email and attachment were reviewed."""
    required = (
        "recipient_email",
        "subject",
        "body",
        "attachment_document_id",
        "attachment_sha256",
    )
    for key in required:
        if not isinstance(reviewed.get(key), str) or not reviewed[key].strip():
            raise ValueError(f"Missing or invalid reviewed field: {key}")

    approved_at = datetime.now(timezone.utc).isoformat()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """
            SELECT recipient_email, subject, body,
                   attachment_document_id, attachment_sha256, status
            FROM job_email_drafts
            WHERE draft_id = ?
            """,
            (draft_id,),
        ).fetchone()

        if row is None:
            connection.rollback()
            return None

        if row["status"] != "pending":
            connection.rollback()
            raise ValueError("Only pending drafts can be approved.")

        for key in required:
            if row[key] != reviewed[key]:
                connection.rollback()
                raise ValueError(
                    f"Reviewed {key} does not match the saved draft."
                )

        connection.execute(
            """
            UPDATE job_email_drafts
            SET status = 'approved', approved_at = ?
            WHERE draft_id = ? AND status = 'pending'
            """,
            (approved_at, draft_id),
        )
        connection.commit()
    finally:
        connection.close()

    return get_draft(draft_id)



def update_pending_draft(draft_id: str, reviewed: dict) -> dict | None:
    """Update editable email fields only while a draft is pending."""
    required = ("recipient_email", "subject", "body")

    for key in required:
        value = reviewed.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing or invalid draft field: {key}")

    if len(reviewed["recipient_email"]) > 500:
        raise ValueError("Recipient email is too long.")
    if len(reviewed["subject"]) > 500:
        raise ValueError("Email subject is too long.")
    if len(reviewed["body"]) > 10000:
        raise ValueError("Email body is too long.")

    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(
            "SELECT status FROM job_email_drafts WHERE draft_id = ?",
            (draft_id,),
        ).fetchone()

        if row is None:
            connection.rollback()
            return None

        if row["status"] != "pending":
            connection.rollback()
            raise ValueError("Only pending drafts can be edited.")

        connection.execute(
            """
            UPDATE job_email_drafts
            SET recipient_email = ?, subject = ?, body = ?
            WHERE draft_id = ? AND status = 'pending'
            """,
            (
                reviewed["recipient_email"].strip(),
                reviewed["subject"].strip(),
                reviewed["body"].strip(),
                draft_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    return get_draft(draft_id)


def mark_draft_sent(draft_id: str) -> dict | None:
    """Mark an approved draft as sent. Only approved drafts can be sent."""
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT status FROM job_email_drafts WHERE draft_id = ?",
            (draft_id,),
        ).fetchone()

        if row is None:
            connection.rollback()
            return None

        if row["status"] != "approved":
            connection.rollback()
            raise ValueError("Only approved drafts can be marked as sent.")

        sent_at = datetime.now(timezone.utc).isoformat()
        connection.execute(
            """
            UPDATE job_email_drafts
            SET status = 'sent', sent_at = ?
            WHERE draft_id = ? AND status = 'approved'
            """,
            (sent_at, draft_id),
        )
        connection.commit()
    finally:
        connection.close()

    return get_draft(draft_id)
