"""
Translate Claude's structured JSON into Photoroom Image API v2/edit multipart fields.

The LLM never sees image bytes; it only emits parameter keys (snake_case) that we
validate, normalize, and rename to dotted Photoroom form keys (e.g. shadow.mode).
"""

from __future__ import annotations

import re
from typing import Any

ALLOWED_REFERENCE_BOX = frozenset({"originalImage"})
# Photoroom v2/edit — only these strings may appear in multipart data (LLM output is untrusted).
ALLOWED_SHADOW_MODE = frozenset({"none", "ai.soft", "ai.hard", "ai.floating"})
ALLOWED_LIGHTING_MODE = frozenset({"ai.auto", "ai.preserve-hue-and-saturation"})
ALLOWED_SCALING = frozenset({"fit", "fill"})

_OUTPUT_SIZE_RE = re.compile(r"^\d+x\d+$")
_HEX_COLOR_RE = re.compile(r"^[0-9A-Fa-f]{6}$")


def normalize_and_validate_dynamic_edit(
    data: dict[str, Any],
) -> tuple[dict[str, str], bool, str | None]:
    """
    Build Photoroom v2/edit `data` dict (all string values), plus orchestration flags.

    Returns:
        (form_fields, segment_first, user_message)

    Raises:
        ValueError: invalid or unsupported parameter values from the model.
    """
    if not isinstance(data, dict):
        raise ValueError("Edit payload must be a JSON object.")

    segment_first = _coerce_bool(data.get("segment_first"), default=False)

    raw_msg = data.get("user_message")
    if raw_msg is not None and not isinstance(raw_msg, str):
        raise ValueError("user_message must be a string when present.")
    user_message = (raw_msg or "").strip() or None

    ref = data.get("reference_box") or data.get("referenceBox") or "originalImage"
    if not isinstance(ref, str):
        raise ValueError("reference_box must be a string.")
    ref_norm = ref.strip()
    if ref_norm.lower().replace("_", "") == "originalimage":
        ref_norm = "originalImage"
    if ref_norm not in ALLOWED_REFERENCE_BOX:
        raise ValueError(
            f"Unsupported reference_box {ref_norm!r}; use originalImage."
        )

    bg_prompt = _optional_str(data.get("background_prompt"))
    bg_color = _optional_plain_str(data.get("background_color"))
    if bg_color and bg_color.startswith("#"):
        bg_color = bg_color[1:]
    if bg_color and not _HEX_COLOR_RE.match(bg_color):
        raise ValueError(
            "background_color must be 6 hex digits, optional leading #."
        )

    out: dict[str, str] = {"referenceBox": ref_norm}

    # If both are set, AI scene wins (matches specs/plan: avoid conflicting v2/edit fields).
    if bg_prompt:
        out["background.prompt"] = bg_prompt
        out.pop("background.color", None)
    elif bg_color:
        out["background.color"] = bg_color.upper()
    else:
        # Resize-only style requests still need a valid v2/edit background field.
        out["background.color"] = "FFFFFF"

    padding = _scalar_str(data.get("padding"), "padding")
    margin = _scalar_str(data.get("margin"), "margin")
    if padding is not None:
        _validate_unit_fraction("padding", padding)
        out["padding"] = padding
    if margin is not None:
        _validate_unit_fraction("margin", margin)
        out["margin"] = margin

    # Strict filter: invalid enum strings are never added to `out` (silent drop — do not send to Photoroom).
    _apply_shadow_mode_filter(data, out)
    _apply_lighting_mode_filter(data, out)
    _apply_background_seed_filter(data, out)
    _apply_blending_defaults(out)

    ospec = _scalar_str(data.get("output_size"), "output_size")
    if ospec is not None:
        if not _OUTPUT_SIZE_RE.match(ospec):
            raise ValueError(
                "output_size must look like WIDTHxHEIGHT with digits (e.g. 1080x1080)."
            )
        out["outputSize"] = ospec

    sc = _optional_str(data.get("scaling"))
    if sc is not None:
        if sc not in ALLOWED_SCALING:
            raise ValueError(f"Unsupported scaling {sc!r}.")
        out["scaling"] = sc

    return out, segment_first, user_message


def _apply_shadow_mode_filter(data: dict[str, Any], out: dict[str, str]) -> None:
    raw = _optional_str(data.get("shadow_mode"))
    if raw is None:
        return
    v = raw.strip().lower()
    if v in ALLOWED_SHADOW_MODE:
        out["shadow.mode"] = v


def _apply_lighting_mode_filter(data: dict[str, Any], out: dict[str, str]) -> None:
    raw = _optional_str(data.get("lighting_mode"))
    if raw is None:
        return
    v = raw.strip().lower()
    if v in ALLOWED_LIGHTING_MODE:
        out["lighting.mode"] = v


def _apply_background_seed_filter(data: dict[str, Any], out: dict[str, str]) -> None:
    """
    Accept optional seed and map it to background.seed.
    Only integers are accepted (or numeric strings that parse as integers).
    """
    raw = data.get("seed")
    if raw is None:
        raw = data.get("background_seed")
    if raw is None:
        return
    if isinstance(raw, bool):
        return
    try:
        seed_value = int(raw)
    except (ValueError, TypeError):
        return
    out["background.seed"] = str(seed_value)


def _apply_blending_defaults(out: dict[str, str]) -> None:
    """
    Force baseline product-to-background blending when not explicitly set.
    - lighting.mode defaults to ai.auto
    - shadow.mode defaults to ai.soft
    """
    if "lighting.mode" not in out:
        out["lighting.mode"] = "ai.auto"
    if "shadow.mode" not in out:
        out["shadow.mode"] = "ai.soft"


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    return s or None


def _optional_plain_str(value: Any) -> str | None:
    """String-only optional field (e.g. hex color)."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("background_color must be a string when provided.")
    s = value.strip()
    return s or None


def _scalar_str(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        s = str(value).strip()
        return s or None
    if isinstance(value, str):
        s = value.strip()
        return s or None
    raise ValueError(f"{field} must be a string or number when provided.")


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"true", "1", "yes"}:
            return True
        if low in {"false", "0", "no"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _validate_unit_fraction(label: str, value: str) -> None:
    try:
        x = float(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a decimal string.") from exc
    if not 0 <= x <= 1:
        raise ValueError(f"{label} must be between 0 and 1.")
