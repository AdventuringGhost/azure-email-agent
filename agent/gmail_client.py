"""Gmail API client: authenticate via OAuth2 credentials, poll, read, mark, reply."""
import base64
import json
import logging
from email.mime.text import MIMEText
from typing import Iterator

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailClient:
    def __init__(self, credentials_json: str) -> None:
        creds_data = json.loads(credentials_json)
        creds = Credentials.from_authorized_user_info(creds_data, _SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        self._svc = build("gmail", "v1", credentials=creds)

    # ------------------------------------------------------------------
    def get_unread_emails(self) -> Iterator[dict]:
        result = (
            self._svc.users()
            .messages()
            .list(userId="me", q="is:unread in:inbox")
            .execute()
        )
        for ref in result.get("messages", []):
            msg = (
                self._svc.users()
                .messages()
                .get(userId="me", id=ref["id"], format="full")
                .execute()
            )
            yield self._parse(msg)

    def mark_as_read(self, message_id: str) -> None:
        self._svc.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()
        logger.debug("Marked %s as read", message_id)

    def send_reply(self, thread_id: str, to: str, subject: str, body: str) -> None:
        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        mime = MIMEText(body)
        mime["to"] = to
        mime["subject"] = reply_subject
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        self._svc.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": thread_id},
        ).execute()
        logger.info("Reply sent to %s on thread %s", to, thread_id)

    # ------------------------------------------------------------------
    def _parse(self, msg: dict) -> dict:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        return {
            "id": msg["id"],
            "thread_id": msg["threadId"],
            "subject": headers.get("Subject", "(no subject)"),
            "sender": headers.get("From", ""),
            "body": self._extract_body(msg["payload"]),
        }

    def _extract_body(self, payload: dict) -> str:
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"].get("data", "")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore") if data else ""
