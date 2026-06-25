"""Automatic JSON report delivery via the Gmail API (assignment §9).

Uses an OAuth Desktop client (``credentials.json`` -> cached ``token.json``) per
the course Google API guide. Token-based auth replaces passwords; the email body
contains *only* the JSON report so the grading harness can parse it directly.

Google libraries are imported lazily so the rest of the package runs without them.
"""

from __future__ import annotations

import base64
import json
import os
from email.message import EmailMessage
from pathlib import Path

# Minimal scope needed to send mail (the course guide's gmail.modify also works).
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def load_credentials(credentials_file: str, token_file: str):
    """Return valid OAuth credentials, running the consent flow on first use."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    token_path = Path(token_file)
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _encode(
    report: dict, recipient: str, subject: str, sender: str | None, indent: int | None = 2
) -> dict:
    """Build a Gmail raw payload whose body is exactly the JSON report.

    ``indent=None`` produces the compact single-line form ``json.dumps(report)``
    used for the inter-group bonus report so both teams' bodies match.
    """
    message = EmailMessage()
    message.set_content(json.dumps(report, indent=indent))  # body = JSON only, no extra text
    message["To"] = recipient
    message["Subject"] = subject
    if sender:
        message["From"] = sender
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}


def send_report(
    report: dict,
    recipient: str,
    *,
    credentials_file: str = "credentials.json",
    token_file: str = "token.json",
    subject: str = "HW6 Cop-Thief Report",
    sender: str | None = None,
    indent: int | None = 2,
) -> str:
    """Send ``report`` as JSON to ``recipient`` and return the Gmail message id."""
    from googleapiclient.discovery import build

    creds = load_credentials(credentials_file, token_file)
    service = build("gmail", "v1", credentials=creds)
    body = _encode(report, recipient, subject, sender, indent)
    sent = service.users().messages().send(userId="me", body=body).execute()
    return sent["id"]


def send_report_from_env(
    report: dict, default_recipient: str, subject: str = "HW6 Cop-Thief Report",
    indent: int | None = 2,
) -> str:
    """Send using ``GMAIL_*`` / ``REPORT_RECIPIENT`` environment configuration."""
    return send_report(
        report,
        recipient=os.getenv("REPORT_RECIPIENT", default_recipient),
        indent=indent,
        credentials_file=os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json"),
        token_file=os.getenv("GMAIL_TOKEN_FILE", "token.json"),
        subject=subject,
    )
