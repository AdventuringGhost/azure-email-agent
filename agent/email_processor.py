"""Orchestrates GmailClient and ClaudeClient: classify, log, optionally reply."""
import logging

from agent.claude_client import ClaudeClient
from agent.config import Config
from agent.gmail_client import GmailClient

logger = logging.getLogger(__name__)


class EmailProcessor:
    def __init__(self, config: Config) -> None:
        self._gmail = GmailClient(config.gmail_credentials_json)
        self._claude = ClaudeClient(
            api_key=config.foundry_api_key,
            deployment=config.foundry_deployment,
        )

    def process_unread(self) -> int:
        """Process all unread inbox emails. Returns the count handled."""
        count = 0
        for email in self._gmail.get_unread_emails():
            self._handle(email)
            count += 1
        return count

    # ------------------------------------------------------------------
    def _handle(self, email: dict) -> None:
        msg_id = email["id"]
        subject = email["subject"]
        sender = email["sender"]

        logger.info("Email from %s | subject: %s", sender, subject)

        result = self._claude.process_email(
            subject=subject,
            body=email["body"],
            sender=sender,
        )
        category = result.get("category", "routine")
        summary = result.get("summary", "")
        draft_reply = result.get("draft_reply", "")

        logger.info("Classified as '%s' — %s", category, summary)

        self._gmail.mark_as_read(msg_id)

        if category == "spam":
            logger.info("Spam — skipping reply for '%s'", subject)
            return

        if draft_reply:
            self._gmail.send_reply(
                thread_id=email["thread_id"],
                to=sender,
                subject=subject,
                body=draft_reply,
            )
        else:
            logger.warning("No draft reply generated for '%s'", subject)
