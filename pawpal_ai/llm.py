"""Optional LLM access.

PawPal+ works with no model at all: the agent falls back to a deterministic
template narrative. If ANTHROPIC_API_KEY is set, ``default_client()`` returns a
client that calls the Anthropic Messages API over plain HTTPS (standard library
only, no SDK needed). Any failure returns None so the caller can fall back.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional, Protocol


class LLMClient(Protocol):
    name: str

    def complete(self, system: str, user: str) -> Optional[str]:
        """Return the model's text, or None if the call failed."""


class AnthropicClient:
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: Optional[str] = None, timeout: float = 20.0):
        self.api_key = api_key
        self.model = model or os.environ.get("PAWPAL_MODEL", "claude-sonnet-5-5")
        self.timeout = timeout
        self.name = f"anthropic:{self.model}"

    def complete(self, system: str, user: str) -> Optional[str]:
        body = json.dumps({
            "model": self.model,
            "max_tokens": 600,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }).encode("utf-8")
        request = urllib.request.Request(self.URL, data=body, headers={
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        })
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
            return "".join(b.get("text", "") for b in data.get("content", [])
                           if b.get("type") == "text") or None
        except Exception:  # network, auth, quota, malformed reply: caller falls back
            return None


class ScriptedLLM:
    """A fake model that returns a fixed reply. Used in tests and the evaluation harness."""

    def __init__(self, reply: Optional[str], name: str = "scripted"):
        self.reply = reply
        self.name = name
        self.calls = 0
        self.last_user: str = ""   # the facts the model was shown, for inspection in tests

    def complete(self, system: str, user: str) -> Optional[str]:
        self.calls += 1
        self.last_user = user
        return self.reply


def default_client() -> Optional[LLMClient]:
    """Return a real client when an API key is configured, otherwise None."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return AnthropicClient(key) if key else None
