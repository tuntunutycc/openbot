import json
import os
import re
from typing import Any

import anthropic

DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
PLACEHOLDER_KEYS = frozenset({"", "your_anthropic_key_here"})


class AnthropicPipelineError(Exception):
    """Raised when caption parsing via Claude fails."""


_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AnthropicPipelineError("Model returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise AnthropicPipelineError("Model JSON must be an object.")
    return data


def _call_claude(client: anthropic.Anthropic, system: str, user: str) -> str:
    model = os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
    msg = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts: list[str] = []
    for block in msg.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts).strip()


def parse_caption(user_caption: str) -> tuple[str, str]:
    """
    Parse user caption into (photoroom_background_prompt, marketing_copy).

    Returns two non-empty strings or raises AnthropicPipelineError.
    """
    caption = (user_caption or "").strip()
    if not caption:
        raise AnthropicPipelineError("Caption is empty.")

    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key in PLACEHOLDER_KEYS:
        raise AnthropicPipelineError("Anthropic API key is not configured.")

    system = (
        "You help build e-commerce ad creatives. "
        "Reply with ONLY a single JSON object, no markdown, no other text. "
        "Keys exactly: "
        '"photoroom_background_prompt" (string, detailed English scene description for an AI background generator: lighting, setting, mood; describe only the background, not the product), '
        '"marketing_copy" (string, short marketing headline and one paragraph suitable for social or catalog). '
        "Both values must be non-empty strings."
    )
    user = f"User instruction for the product photo ad:\n{caption}"

    client = anthropic.Anthropic(api_key=key)
    raw = _call_claude(client, system, user)

    try:
        data = _extract_json_object(raw)
    except AnthropicPipelineError:
        fix_user = (
            "Your previous reply was not valid JSON. "
            "Output ONLY one JSON object with keys photoroom_background_prompt and marketing_copy (strings). No markdown."
            f"\nOriginal instruction:\n{caption}"
        )
        raw = _call_claude(client, system, fix_user)
        data = _extract_json_object(raw)

    bg = data.get("photoroom_background_prompt")
    mk = data.get("marketing_copy")
    if not isinstance(bg, str) or not isinstance(mk, str):
        raise AnthropicPipelineError("JSON must contain string photoroom_background_prompt and marketing_copy.")
    bg, mk = bg.strip(), mk.strip()
    if not bg or not mk:
        raise AnthropicPipelineError("Model returned empty prompt or marketing copy.")

    return bg, mk
