"""AEGISCORE_PHASE10_GMAIL

Gmail API integration for job application email delivery.

Supports both mocked delivery (for automated testing) and real Gmail API
delivery (when OAuth2 credentials are configured). Never sends email
without explicit user approval.

Configuration (environment variables):
    AEGISCORE_GMAIL_CLIENT_ID     OAuth2 client ID (required for real delivery)
    AEGISCORE_GMAIL_CLIENT_SECRET OAuth2 client secret (required for real delivery)
    AEGISCORE_GMAIL_REDIRECT_URI  OAuth2 redirect URI (default: http://localhost:8080/callback)
    AEGISCORE_GMAIL_MOCK_MODE     Set to "false" to attempt real Gmail API delivery
                                  (requires valid credentials). Default: true when
                                  credentials are not configured.
"""

from __future__ import annotations

import base64
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

GMAIL_CLIENT_ID = os.environ.get("AEGISCORE_GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.environ.get("AEGISCORE_GMAIL_CLIENT_SECRET", "")
GMAIL_REDIRECT_URI = os.environ.get(
    "AEGISCORE_GMAIL_REDIRECT_URI", "http://localhost:8080/callback"
)
_GMAIL_CREDENTURED = bool(GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET)


class GmailService:
    """Gmail API client with mandatory mock mode for testing.

    When Gmail OAuth2 credentials are not configured (or AEGISCORE_GMAIL_MOCK_MODE
    is set), all delivery is mocked: the send call succeeds but no real email
    is transmitted. This guarantees no real email is ever sent during automated
    testing or without explicit configuration.
    """

    def __init__(self, mock_mode: bool | None = None) -> None:
        if mock_mode is None:
            mock_mode = not _GMAIL_CREDENTURED or os.environ.get(
                "AEGISCORE_GMAIL_MOCK_MODE", "true"
            ).lower() == "true"
        self.mock_mode = mock_mode

    def is_configured(self) -> bool:
        """Return True if real Gmail API credentials are configured and not mocked."""
        return _GMAIL_CREDENTURED and not self.mock_mode

    def requires_credentials(self) -> bool:
        """Return True if real delivery is requested but credentials are missing."""
        return not self.mock_mode and not _GMAIL_CREDENTURED

    def send_email(
        self,
        draft: dict[str, Any],
        attachment_path: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Send an email draft via Gmail API (or mock).

        Args:
            draft: The approved email draft dictionary (recipient_email,
                subject, body, attachment_document_id, etc.).
            attachment_path: Optional path to the attachment file.
            confirm: Must be True to actually send. Explicit user approval
                is required before this method is called.

        Returns:
            A dictionary with send result metadata. In mock mode, ``mock``
            is True and no real delivery occurs.

        Raises:
            ValueError: If confirm is not True (no explicit approval).
            RuntimeError: If real delivery is attempted but credentials
                are missing or misconfigured.
        """
        if not confirm:
            raise ValueError(
                "Explicit confirmation is required to send email. "
                "Set confirm=True only after user has approved the draft."
            )

        recipient = draft.get("recipient_email", "")
        subject = draft.get("subject", "")
        body = draft.get("body", "")

        if self.mock_mode:
            return {
                "sent": True,
                "mock": True,
                "provider": "gmail-mock",
                "message": (
                    "Email sent in mock mode. No real email was delivered. "
                    "Configure AEGISCORE_GMAIL_CLIENT_ID and "
                    "AEGISCORE_GMAIL_CLIENT_SECRET for real Gmail API delivery."
                ),
                "recipient": recipient,
                "subject": subject,
                "attachment_included": attachment_path is not None,
            }

        # Real Gmail API delivery path (requires OAuth2 credentials).
        if not _GMAIL_CREDENTURED:
            raise RuntimeError(
                "Real Gmail delivery requested but OAuth2 credentials are not "
                "configured. Set AEGISCORE_GMAIL_CLIENT_ID and "
                "AEGISCORE_GMAIL_CLIENT_SECRET, or leave mock mode enabled."
            )

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "Gmail API delivery requires google-auth-oauthlib and "
                "google-api-python-client. Install them or enable mock mode."
            ) from exc

        mime_message = MIMEMultipart()
        mime_message["to"] = recipient
        mime_message["subject"] = subject
        mime_message.attach(MIMEText(body, "plain"))

        if attachment_path:
            try:
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(
                        f.read(), Name=os.path.basename(attachment_path)
                    )
                part["Content-Disposition"] = (
                    f'attachment; filename="{os.path.basename(attachment_path)}"'
                )
                mime_message.attach(part)
            except OSError as exc:
                raise RuntimeError(f"Could not read attachment file: {exc}") from exc

        raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode("utf-8")

        try:
            creds = Credentials(
                token=os.environ.get("AEGISCORE_GMAIL_ACCESS_TOKEN", ""),
                refresh_token=os.environ.get("AEGISCORE_GMAIL_REFRESH_TOKEN", ""),
                client_id=GMAIL_CLIENT_ID,
                client_secret=GMAIL_CLIENT_SECRET,
            )
            service = build("gmail", "v1", credentials=creds)
            sent = (
                service.users()
                .messages()
                .send(userId="me", body={"raw": raw})
                .execute()
            )
        except Exception as exc:
            raise RuntimeError(f"Gmail API send failed: {exc}") from exc

        return {
            "sent": True,
            "mock": False,
            "provider": "gmail",
            "message": "Email delivered via Gmail API.",
            "gmail_message_id": sent.get("id"),
            "recipient": recipient,
            "subject": subject,
            "attachment_included": attachment_path is not None,
        }


def get_gmail_service() -> GmailService:
    """Return a GmailService instance (mock mode unless credentials configured)."""
    return GmailService()