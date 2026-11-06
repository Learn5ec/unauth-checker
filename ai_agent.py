import os
import json
import requests

# Claude Code stores its gateway credentials in ~/.claude/settings.json under an
# "env" block (ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL / ANTHROPIC_MODEL).
# We reuse that so no separate Mistral key is required.
DEFAULT_SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")
DEFAULT_BASE_URL = "https://api.anthropic.com"
DEFAULT_MODEL = "claude-sonnet-5"
ANTHROPIC_VERSION = "2023-06-01"


def _load_claude_code_settings():
    """Read the `env` block from ~/.claude/settings.json, if present."""
    path = os.environ.get("CLAUDE_SETTINGS_PATH", DEFAULT_SETTINGS_PATH)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return (json.load(f) or {}).get("env", {}) or {}
    except Exception:
        return {}


class AIAgent:
    """Generates realistic sample parameter values via the Claude (Anthropic)
    Messages API, reusing the credentials already configured for Claude Code."""

    def __init__(self):
        settings = _load_claude_code_settings()

        # Precedence: explicit env vars, then Claude Code settings.json, then defaults.
        self.api_key = (
            os.getenv("ANTHROPIC_AUTH_TOKEN")
            or os.getenv("ANTHROPIC_API_KEY")
            or settings.get("ANTHROPIC_AUTH_TOKEN")
            or settings.get("ANTHROPIC_API_KEY")
        )
        self.base_url = (
            os.getenv("ANTHROPIC_BASE_URL")
            or settings.get("ANTHROPIC_BASE_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self.model = (
            os.getenv("ANTHROPIC_MODEL")
            or settings.get("ANTHROPIC_MODEL")
            or DEFAULT_MODEL
        )
        self.endpoint = f"{self.base_url}/v1/messages"

        if not self.api_key:
            raise RuntimeError(
                "No Anthropic API key found. Set ANTHROPIC_AUTH_TOKEN / "
                "ANTHROPIC_API_KEY, configure ~/.claude/settings.json, or run "
                "with --skip-ai-params to bypass AI parameter generation."
            )

    @staticmethod
    def _extract_text(payload: dict) -> str:
        """Pull the assistant text out of an Anthropic Messages response."""
        content = payload.get("content", [])
        if isinstance(content, str):
            return content.strip()
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts).strip()

    def generate_sample_value(self, param_type: str, name: str, description: str) -> str:
        prompt = (
            "Generate a realistic example value for an API parameter.\n"
            f"Name: {name}\n"
            f"Type: {param_type}\n"
            f"Description: {description}\n"
            "Return only the value, with no explanation, quotes, or formatting."
        )

        payload = {
            "model": self.model,
            "max_tokens": 64,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": prompt}],
        }

        headers = {
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        # The official Anthropic API expects `x-api-key`; custom OAuth-style
        # gateways (e.g. the Claude Code proxy) expect `Authorization: Bearer`.
        # Sending both is rejected by the official API, so choose one.
        if "api.anthropic.com" in self.base_url:
            headers["x-api-key"] = self.api_key
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            r = requests.post(self.endpoint, json=payload, headers=headers, timeout=20)
            r.raise_for_status()
            value = self._extract_text(r.json())
            return value if value else "test"
        except Exception:
            return "test"
