import base64
import json
import os
from typing import Any

import requests

DEFAULT_SEGMENT_URL = "https://sdk.photoroom.com/v1/segment"
DEFAULT_TIMEOUT_SECONDS = 120
PLACEHOLDER_KEYS = frozenset({"", "your_photoroom_key_here"})


class PhotoroomError(Exception):
    """Raised when Photoroom API calls fail or configuration is invalid."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


def _user_safe_message(status_code: int | None, detail: str | None) -> str:
    if status_code == 400:
        return "Could not process this image. Try a different photo or format."
    if status_code in (401, 403):
        return "Photoroom API key is missing, invalid, or not allowed."
    if status_code == 402:
        return "Photoroom billing or quota issue. Check your Photoroom plan."
    if status_code == 429:
        return "Too many requests to Photoroom. Please try again shortly."
    if status_code is not None and status_code >= 500:
        return "Photoroom is temporarily unavailable. Please try again later."
    if detail:
        return f"Image processing failed: {detail}"
    return "Image processing failed. Please try again later."


def _parse_error_payload(text: str) -> str | None:
    try:
        data: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data.get("detail") or data.get("message")


def remove_background(
    image_bytes: bytes,
    *,
    filename: str | None = None,
    api_key: str | None = None,
    segment_url: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    output_format: str = "png",
    size: str = "medium",
    channels: str = "rgba",
    **extra_fields: str,
) -> bytes:
    """
    Call Photoroom Remove Background (POST /v1/segment).

    extra_fields may include crop, despill, bg_color, etc., as string values per API.
    """
    if not image_bytes:
        raise PhotoroomError("Empty image data.")

    key = api_key if api_key is not None else os.getenv("PHOTOROOM_API_KEY", "")
    if not key or key in PLACEHOLDER_KEYS:
        raise PhotoroomError("Photoroom API key is not configured in the environment.")

    url = segment_url or os.getenv("PHOTOROOM_SEGMENT_URL") or DEFAULT_SEGMENT_URL
    safe_name = filename or "image.jpg"
    files = {"image_file": (safe_name, image_bytes)}
    data: dict[str, str] = {
        "format": output_format,
        "size": size,
        "channels": channels,
    }
    for k, v in extra_fields.items():
        if v is not None:
            data[k] = str(v)

    try:
        response = requests.post(
            url,
            headers={"x-api-key": key},
            files=files,
            data=data,
            timeout=timeout_seconds,
        )
    except requests.exceptions.Timeout as exc:
        raise PhotoroomError("Photoroom request timed out. Try again.") from exc
    except requests.exceptions.RequestException as exc:
        raise PhotoroomError("Network error talking to Photoroom. Try again.") from exc

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
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise PhotoroomError("Unexpected JSON response from Photoroom.") from exc
        b64 = payload.get("base64img")
        if not b64 or not isinstance(b64, str):
            raise PhotoroomError("Photoroom returned JSON without base64 image data.")
        try:
            return base64.b64decode(b64)
        except (ValueError, TypeError) as exc:
            raise PhotoroomError("Invalid base64 image data from Photoroom.") from exc

    return response.content
