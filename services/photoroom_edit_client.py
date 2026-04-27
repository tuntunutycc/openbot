import base64
import json
import logging
import os
from typing import Any

import requests

from services.catalog_styles import CatalogStyle
from services.photoroom_client import PhotoroomError, _parse_error_payload, _user_safe_message

logger = logging.getLogger(__name__)

DEFAULT_EDIT_URL = "https://image-api.photoroom.com/v2/edit"
DEFAULT_TIMEOUT_SECONDS = 180
PLACEHOLDER_KEYS = frozenset({"", "your_photoroom_key_here"})


def _post_v2_edit(
    image_bytes: bytes,
    filename: str,
    form_data: dict[str, str],
    *,
    api_key: str | None = None,
    edit_url: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    model_version_header: str | None = None,
    quota_fallback_bytes: bytes,
) -> bytes:
    """
    Shared POST handler for Photoroom v2/edit (multipart imageFile + string fields).

    quota_fallback_bytes: returned on HTTP 402/403 so callers can recover the last
    good image (e.g. original upload or segment cutout).
    """
    key = api_key if api_key is not None else os.getenv("PHOTOROOM_API_KEY", "")
    if not key or key in PLACEHOLDER_KEYS:
        raise PhotoroomError("Photoroom API key is not configured in the environment.")

    url = edit_url or os.getenv("PHOTOROOM_EDIT_URL") or DEFAULT_EDIT_URL
    headers: dict[str, str] = {"x-api-key": key}
    mv = model_version_header or os.getenv("PHOTOROOM_AI_MODEL_VERSION")
    if mv:
        headers["pr-ai-background-model-version"] = mv

    files = {"imageFile": (filename, image_bytes)}

    try:
        response = requests.post(
            url,
            headers=headers,
            files=files,
            data=form_data,
            timeout=timeout_seconds,
        )
    except requests.exceptions.Timeout as exc:
        raise PhotoroomError("Photoroom Image API request timed out. Try again.") from exc
    except requests.exceptions.RequestException as exc:
        raise PhotoroomError("Network error talking to Photoroom Image API. Try again.") from exc

    if response.status_code in (402, 403):
        logger.warning("Photoroom API Quota exceeded, using fallback image.")
        return quota_fallback_bytes

    if not response.ok:
        detail = _parse_error_payload(response.text) or response.text[:300]
        raise PhotoroomError(
            _user_safe_message(response.status_code, detail),
            status_code=response.status_code,
            detail=detail,
        )

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "application/json" in content_type:
        try:
            payload: dict[str, Any] = response.json()
        except json.JSONDecodeError as exc:
            raise PhotoroomError("Unexpected JSON response from Photoroom Image API.") from exc
        b64 = payload.get("base64img")
        if not b64 or not isinstance(b64, str):
            raise PhotoroomError("Photoroom returned JSON without base64 image data.")
        try:
            return base64.b64decode(b64)
        except (ValueError, TypeError) as exc:
            raise PhotoroomError("Invalid base64 image data from Photoroom.") from exc

    return response.content


def dynamic_edit(
    image_bytes: bytes,
    filename: str,
    form_data: dict[str, str],
    *,
    api_key: str | None = None,
    edit_url: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    model_version_header: str | None = None,
) -> bytes:
    """
    Photoroom v2/edit with caller-supplied multipart fields (dynamic /edit pipeline).

    form_data keys must already match Photoroom's dotted names (e.g. background.prompt).
    On quota/billing responses, returns image_bytes unchanged (same as ai_background).
    """
    if not image_bytes:
        raise PhotoroomError("Empty image data.")
    if not form_data:
        raise PhotoroomError("Edit parameters are empty.")
    return _post_v2_edit(
        image_bytes,
        filename,
        form_data,
        api_key=api_key,
        edit_url=edit_url,
        timeout_seconds=timeout_seconds,
        model_version_header=model_version_header,
        quota_fallback_bytes=image_bytes,
    )


def ai_background(
    cutout_bytes: bytes,
    background_prompt: str,
    *,
    filename: str = "cutout.png",
    api_key: str | None = None,
    edit_url: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    model_version_header: str | None = None,
) -> bytes:
    """
    Photoroom Image Editing API: AI background via POST v2/edit.

    On HTTP 402 or 403 (quota/billing/forbidden plan), logs a warning and returns
    the cutout bytes unchanged so the rest of the pipeline can still be tested.
    """
    if not cutout_bytes:
        raise PhotoroomError("Empty cutout image data.")

    prompt = (background_prompt or "").strip()
    if not prompt:
        raise PhotoroomError("Background prompt is empty.")

    data = {
        "referenceBox": "originalImage",
        "background.prompt": prompt,
    }
    return _post_v2_edit(
        cutout_bytes,
        filename,
        data,
        api_key=api_key,
        edit_url=edit_url,
        timeout_seconds=timeout_seconds,
        model_version_header=model_version_header,
        quota_fallback_bytes=cutout_bytes,
    )


def render_catalog_layout(
    cutout_bytes: bytes,
    style: CatalogStyle,
    *,
    filename: str = "cutout.png",
    background_prompt: str | None = None,
    api_key: str | None = None,
    edit_url: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    model_version_header: str | None = None,
) -> bytes:
    """
    Render a catalog-style output using Photoroom /v2/edit.

    On HTTP 402/403 quota-billing responses, logs a warning and returns the
    cutout unchanged so Telegram end-to-end testing can continue.
    """
    if not cutout_bytes:
        raise PhotoroomError("Empty cutout image data.")

    key = api_key if api_key is not None else os.getenv("PHOTOROOM_API_KEY", "")
    if not key or key in PLACEHOLDER_KEYS:
        raise PhotoroomError("Photoroom API key is not configured in the environment.")

    url = edit_url or os.getenv("PHOTOROOM_EDIT_URL") or DEFAULT_EDIT_URL
    headers: dict[str, str] = {"x-api-key": key}
    mv = model_version_header or os.getenv("PHOTOROOM_AI_MODEL_VERSION")
    if mv:
        headers["pr-ai-background-model-version"] = mv

    files = {"imageFile": (filename, cutout_bytes)}
    data: dict[str, str] = {
        "referenceBox": "originalImage",
        "padding": style.padding,
        "margin": style.margin,
        "shadow.mode": style.shadow_mode,
        "lighting.mode": style.lighting_mode,
        "outputSize": style.output_size,
        "scaling": style.scaling,
    }

    prompt = (background_prompt or "").strip()
    # Prompt always wins; never send background.color together with background.prompt.
    if prompt:
        data["background.prompt"] = prompt
    elif style.use_ai_background:
        data["background.prompt"] = style.default_background_prompt
    else:
        data["background.color"] = style.background_color

    try:
        response = requests.post(
            url,
            headers=headers,
            files=files,
            data=data,
            timeout=timeout_seconds,
        )
    except requests.exceptions.Timeout as exc:
        raise PhotoroomError("Photoroom catalog request timed out. Try again.") from exc
    except requests.exceptions.RequestException as exc:
        raise PhotoroomError("Network error talking to Photoroom Image API. Try again.") from exc

    if response.status_code in (402, 403):
        logger.warning("Photoroom API Quota exceeded, using fallback image.")
        return cutout_bytes

    if not response.ok:
        detail = _parse_error_payload(response.text) or response.text[:300]
        raise PhotoroomError(
            _user_safe_message(response.status_code, detail),
            status_code=response.status_code,
            detail=detail,
        )

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "application/json" in content_type:
        try:
            payload: dict[str, Any] = response.json()
        except json.JSONDecodeError as exc:
            raise PhotoroomError("Unexpected JSON response from Photoroom Image API.") from exc
        b64 = payload.get("base64img")
        if not b64 or not isinstance(b64, str):
            raise PhotoroomError("Photoroom returned JSON without base64 image data.")
        try:
            return base64.b64decode(b64)
        except (ValueError, TypeError) as exc:
            raise PhotoroomError("Invalid base64 image data from Photoroom.") from exc

    return response.content


def render_catalog_layout_with_fallback_flag(
    cutout_bytes: bytes,
    style: CatalogStyle,
    *,
    filename: str = "cutout.png",
    background_prompt: str | None = None,
    background_seed: int | None = None,
    include_output_size: bool = True,
    api_key: str | None = None,
    edit_url: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    model_version_header: str | None = None,
) -> tuple[bytes, bool]:
    """
    Same as render_catalog_layout, but returns (image_bytes, used_quota_fallback).
    """
    if not cutout_bytes:
        raise PhotoroomError("Empty cutout image data.")

    key = api_key if api_key is not None else os.getenv("PHOTOROOM_API_KEY", "")
    if not key or key in PLACEHOLDER_KEYS:
        raise PhotoroomError("Photoroom API key is not configured in the environment.")

    url = edit_url or os.getenv("PHOTOROOM_EDIT_URL") or DEFAULT_EDIT_URL
    headers: dict[str, str] = {"x-api-key": key}
    mv = model_version_header or os.getenv("PHOTOROOM_AI_MODEL_VERSION")
    if mv:
        headers["pr-ai-background-model-version"] = mv

    files = {"imageFile": (filename, cutout_bytes)}
    data: dict[str, str] = {
        "referenceBox": "originalImage",
        "padding": style.padding,
        "margin": style.margin,
        "shadow.mode": style.shadow_mode,
        "lighting.mode": style.lighting_mode,
        "scaling": style.scaling,
    }
    # Keep baseline blending enabled for catalog composition payloads.
    data.setdefault("lighting.mode", "ai.auto")
    data.setdefault("shadow.mode", "ai.soft")
    if include_output_size:
        data["outputSize"] = style.output_size

    prompt = (background_prompt or "").strip()
    # Prompt always wins; never send background.color together with background.prompt.
    if prompt:
        data["background.prompt"] = prompt
        if background_seed is not None:
            data["background.seed"] = str(background_seed)
    elif style.use_ai_background:
        data["background.prompt"] = style.default_background_prompt
        if background_seed is not None:
            data["background.seed"] = str(background_seed)
    else:
        data["background.color"] = style.background_color

    try:
        response = requests.post(
            url,
            headers=headers,
            files=files,
            data=data,
            timeout=timeout_seconds,
        )
    except requests.exceptions.Timeout as exc:
        raise PhotoroomError("Photoroom catalog request timed out. Try again.") from exc
    except requests.exceptions.RequestException as exc:
        raise PhotoroomError("Network error talking to Photoroom Image API. Try again.") from exc

    if response.status_code in (402, 403):
        logger.warning("Photoroom API Quota exceeded, using fallback image.")
        return cutout_bytes, True

    if not response.ok:
        detail = _parse_error_payload(response.text) or response.text[:300]
        raise PhotoroomError(
            _user_safe_message(response.status_code, detail),
            status_code=response.status_code,
            detail=detail,
        )

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "application/json" in content_type:
        try:
            payload: dict[str, Any] = response.json()
        except json.JSONDecodeError as exc:
            raise PhotoroomError("Unexpected JSON response from Photoroom Image API.") from exc
        b64 = payload.get("base64img")
        if not b64 or not isinstance(b64, str):
            raise PhotoroomError("Photoroom returned JSON without base64 image data.")
        try:
            return base64.b64decode(b64), False
        except (ValueError, TypeError) as exc:
            raise PhotoroomError("Invalid base64 image data from Photoroom.") from exc

    return response.content, False
