import base64
import json
import logging
import os
from typing import Any

import requests

from services.photoroom_client import PhotoroomError, _parse_error_payload, _user_safe_message

logger = logging.getLogger(__name__)

DEFAULT_EDIT_URL = "https://image-api.photoroom.com/v2/edit"
DEFAULT_TIMEOUT_SECONDS = 180
PLACEHOLDER_KEYS = frozenset({"", "your_photoroom_key_here"})


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

    key = api_key if api_key is not None else os.getenv("PHOTOROOM_API_KEY", "")
    if not key or key in PLACEHOLDER_KEYS:
        raise PhotoroomError("Photoroom API key is not configured in the environment.")

    url = edit_url or os.getenv("PHOTOROOM_EDIT_URL") or DEFAULT_EDIT_URL
    headers: dict[str, str] = {"x-api-key": key}
    mv = model_version_header or os.getenv("PHOTOROOM_AI_MODEL_VERSION")
    if mv:
        headers["pr-ai-background-model-version"] = mv

    files = {"imageFile": (filename, cutout_bytes)}
    data = {
        "referenceBox": "originalImage",
        "background.prompt": prompt,
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            files=files,
            data=data,
            timeout=timeout_seconds,
        )
    except requests.exceptions.Timeout as exc:
        raise PhotoroomError("Photoroom Image API request timed out. Try again.") from exc
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
