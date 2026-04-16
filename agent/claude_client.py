"""Anthropic SDK client; classifies and drafts email replies."""
import json
import logging

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an email triage assistant. Analyse each email and return ONLY a
JSON object with exactly these fields:
  "category"    – one of: "urgent", "routine", "spam"
  "summary"     – one sentence describing the email
  "draft_reply" – a polite, professional reply (empty string when category is "spam")

Output only the JSON object. No explanation, no markdown fences."""


class ClaudeClient:
    def __init__(self, api_key: str, deployment: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._deployment = deployment

    def process_email(self, subject: str, body: str, sender: str) -> dict:
        """Return dict with keys: category, summary, draft_reply."""
        user_content = f"From: {sender}\nSubject: {subject}\n\n{body}"
        response = self._client.messages.create(
            model=self._deployment,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    # Cache the stable system prompt across repeated calls
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )
        text = next((b.text for b in response.content if b.type == "text"), "{}")
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            logger.error("Failed to parse Claude response as JSON: %.200s", text)
            result = {"category": "routine", "summary": "Parse error.", "draft_reply": ""}

        logger.debug(
            "Cache tokens — created: %s  read: %s",
            response.usage.cache_creation_input_tokens,
            response.usage.cache_read_input_tokens,
        )
        return result
