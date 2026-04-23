import json
import logging
import os
import re
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

# Default model: `claude-3-5-sonnet-20241022` often returns HTTP 400 (retired/unsupported on many keys).
# Override with ANTHROPIC_MODEL; Sonnet 4.5 matches current Anthropic API docs.
DEFAULT_MODEL = "claude-sonnet-4-5"
PLACEHOLDER_KEYS = frozenset({"", "your_anthropic_key_here"})

MOCK_PHOTOROOM_PROMPT = (
    "a beautiful sandy beach with ocean waves, sunny day, professional product photography"
)
MOCK_MARKETING_COPY = (
    "🏖️ [MOCK GENERATED TEXT] Experience the ultimate relaxation! This is a test marketing "
    "copy since the Anthropic API is out of credits. Grab yours today! #SummerVibes"
)


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


def _api_error_detail(exc: anthropic.APIError) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
    return str(exc)


def _should_use_anthropic_mock(exc: BaseException, detail: str) -> bool:
    """True for low-credit / billing-style Anthropic failures so local E2E tests can proceed."""
    d = detail.lower()
    credit_markers = (
        "credit balance",
        "too low to access",
        "insufficient credits",
        "insufficient balance",
        "out of credits",
        "billing",
        "payment required",
        "add credits",
        "purchase credits",
        "quota",
    )
    if any(m in d for m in credit_markers):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code == 402:
            return True
        if exc.status_code in (401, 403):
            if "invalid" in d and "api" in d and "key" in d:
                return False
            if any(
                k in d
                for k in ("credit", "billing", "balance", "payment", "quota", "plan", "subscribe")
            ):
                return True
    # Any other API error (e.g. invalid model): do not mock; surface to caller.
    return False


def _mock_parse_result() -> tuple[str, str]:
    logger.warning("Anthropic API credit low, using mock response.")
    return MOCK_PHOTOROOM_PROMPT, MOCK_MARKETING_COPY


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

    On Anthropic billing/credit or other API failures during the Messages call, returns a
    fixed mock pair so Telegram routing can be tested without credits.
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

    try:
        raw = _call_claude(client, system, user)
    except anthropic.APIError as exc:
        detail = _api_error_detail(exc)
        if _should_use_anthropic_mock(exc, detail):
            return _mock_parse_result()
        logger.warning("Anthropic API error (model=%s): %s", os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL), detail)
        raise AnthropicPipelineError(f"Anthropic request failed: {detail}") from exc

    try:
        data = _extract_json_object(raw)
    except AnthropicPipelineError:
        fix_user = (
            "Your previous reply was not valid JSON. "
            "Output ONLY one JSON object with keys photoroom_background_prompt and marketing_copy (strings). No markdown."
            f"\nOriginal instruction:\n{caption}"
        )
        try:
            raw = _call_claude(client, system, fix_user)
        except anthropic.APIError as exc:
            detail = _api_error_detail(exc)
            if _should_use_anthropic_mock(exc, detail):
                return _mock_parse_result()
            logger.warning(
                "Anthropic API error on JSON retry (model=%s): %s",
                os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
                detail,
            )
            raise AnthropicPipelineError(f"Anthropic request failed: {detail}") from exc
        data = _extract_json_object(raw)

    bg = data.get("photoroom_background_prompt")
    mk = data.get("marketing_copy")
    if not isinstance(bg, str) or not isinstance(mk, str):
        raise AnthropicPipelineError("JSON must contain string photoroom_background_prompt and marketing_copy.")
    bg, mk = bg.strip(), mk.strip()
    if not bg or not mk:
        raise AnthropicPipelineError("Model returned empty prompt or marketing copy.")

    return bg, mk
