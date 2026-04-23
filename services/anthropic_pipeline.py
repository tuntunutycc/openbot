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
_WORD_RE = re.compile(r"[a-z0-9']+")

SINGLE_PROMPT_SYSTEM = (
    "You are a Master Prompt Engineer for commercial product imaging. "
    "The user may write in Burmese or English. "
    "If Burmese: understand intent precisely, translate naturally to English, then enhance professionally. "
    "If English: keep the original intent and professionally enhance directly in English. "
    "Output ONLY one JSON object with keys: "
    '"photoroom_background_prompt" (string) and "marketing_copy" (string). '
    "For photoroom_background_prompt: preserve user meaning, avoid scene drift, and enrich with pro photography language when appropriate "
    "(cinematic lighting, depth of field, photorealistic detail, 8k-quality style wording, commercial composition). "
    "Do not mention APIs, JSON, or internal logic in values. "
    "For marketing_copy: concise ecommerce-ready copy with strong but natural tone."
)

BATCH_PROMPT_SYSTEM = (
    "You are a Master Prompt Engineer for e-commerce catalog generation. "
    "The user may provide Burmese or English instructions. "
    "If Burmese: extract intent precisely, translate to English, then enhance. "
    "If English: preserve intent and enhance directly. "
    "In all cases, final prompts must be professional English. "
    "Output ONLY a JSON array of exactly 3 objects with keys style_name and background_prompt. "
    'style_name must be exactly one each of: "minimal", "lifestyle", "premium". '
    "All three prompts must be highly distinct in scene, mood, and composition while still faithful to the same core product intent. "
    "Use professional photography language (lighting direction, depth cues, photorealistic commercial quality, lens/composition style) where suitable."
)


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


def _extract_json_array(text: str) -> list[Any]:
    text = text.strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AnthropicPipelineError("Model returned invalid JSON array.") from exc
    if not isinstance(data, list):
        raise AnthropicPipelineError("Model JSON must be an array.")
    return data


def _tokenize_for_similarity(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def _is_distinct_prompt_pair(a: str, b: str) -> bool:
    ta = _tokenize_for_similarity(a)
    tb = _tokenize_for_similarity(b)
    if not ta or not tb:
        return False
    overlap = len(ta & tb)
    union = len(ta | tb)
    jaccard = overlap / union if union else 1.0
    return jaccard < 0.72


def _api_error_detail(exc: anthropic.APIError) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
    return str(exc)


def _should_use_anthropic_mock(exc: BaseException, detail: str) -> bool:
    """
    Use mock output for credit/billing failures, or broadly for non–BadRequest API errors
    (rate limits, overload, etc.) so E2E Telegram routing works without a healthy Anthropic account.

    Still surfaces likely **invalid API key** and **invalid model** BadRequests (no credit keywords).
    """
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
    if isinstance(exc, anthropic.BadRequestError):
        # Keep real 400s visible when they look like model/parameter issues, not billing.
        return any(m in d for m in credit_markers)
    if isinstance(exc, anthropic.AuthenticationError):
        if "invalid" in d and "key" in d:
            return False
        return True
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code == 402:
            return True
        if exc.status_code == 403:
            if "invalid" in d and "key" in d:
                return False
            return True
    if isinstance(exc, anthropic.APIError):
        return True
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

    system = SINGLE_PROMPT_SYSTEM
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


def _default_catalog_variation_prompts() -> list[dict[str, str]]:
    return [
        {
            "style_name": "minimal",
            "background_prompt": (
                "clean minimalist studio background, soft white tones, subtle shadow, "
                "high-end product catalog look"
            ),
        },
        {
            "style_name": "premium",
            "background_prompt": (
                "premium luxury catalog setting, warm beige textures, elegant lighting, "
                "sophisticated commercial photography style"
            ),
        },
        {
            "style_name": "lifestyle",
            "background_prompt": (
                "vibrant lifestyle catalog scene, colorful modern environment, energetic mood, "
                "professional product photography composition"
            ),
        },
    ]


def parse_catalog_variation_prompts(user_instruction: str) -> list[dict[str, str]]:
    """
    Return exactly 3 variation prompt objects for catalog generation:
    [{"style_name": "...", "background_prompt": "..."}, ...]
    """
    instruction = (user_instruction or "").strip()
    if not instruction:
        return _default_catalog_variation_prompts()

    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key in PLACEHOLDER_KEYS:
        return _default_catalog_variation_prompts()

    system = BATCH_PROMPT_SYSTEM
    user = f"Catalog instruction:\n{instruction}"
    client = anthropic.Anthropic(api_key=key)

    def _parse_variation_json(raw: str) -> list[dict[str, str]]:
        data = _extract_json_array(raw)
        if len(data) != 3:
            raise AnthropicPipelineError("Catalog variations must be an array of exactly 3 items.")
        out: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                raise AnthropicPipelineError("Each variation item must be an object.")
            style = item.get("style_name")
            prompt = item.get("background_prompt")
            if not isinstance(style, str) or not isinstance(prompt, str):
                raise AnthropicPipelineError("Each variation must include string style_name/background_prompt.")
            style = style.strip().lower()
            prompt = prompt.strip()
            if style not in {"minimal", "premium", "lifestyle"} or not prompt:
                raise AnthropicPipelineError("Invalid style_name or empty background_prompt in variations.")
            out.append({"style_name": style, "background_prompt": prompt})
        styles = {x["style_name"] for x in out}
        if styles != {"minimal", "lifestyle", "premium"}:
            raise AnthropicPipelineError("Variations must include exactly minimal, lifestyle, and premium.")
        p0, p1, p2 = out[0]["background_prompt"], out[1]["background_prompt"], out[2]["background_prompt"]
        if not (_is_distinct_prompt_pair(p0, p1) and _is_distinct_prompt_pair(p0, p2) and _is_distinct_prompt_pair(p1, p2)):
            raise AnthropicPipelineError("Variation prompts are too similar; must be highly distinct.")
        return out

    try:
        raw = _call_claude(client, system, user)
    except anthropic.APIError as exc:
        detail = _api_error_detail(exc)
        if _should_use_anthropic_mock(exc, detail):
            return _default_catalog_variation_prompts()
        return _default_catalog_variation_prompts()

    try:
        return _parse_variation_json(raw)
    except AnthropicPipelineError:
        fix_user = (
            "Your output must be corrected. Output ONLY a JSON array of exactly 3 objects with keys style_name and background_prompt. "
            "Allowed style_name values: minimal, premium, lifestyle. "
            "Use each style exactly once and make prompts highly distinct in mood, environment, and composition."
            f"\nOriginal instruction:\n{instruction}"
        )
        try:
            raw = _call_claude(client, system, fix_user)
            return _parse_variation_json(raw)
        except Exception:
            return _default_catalog_variation_prompts()
