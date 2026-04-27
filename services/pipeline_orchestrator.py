from services.anthropic_pipeline import parse_caption, parse_dynamic_edit_intent
from services.photoroom_client import PhotoroomError, remove_background
from services.photoroom_edit_client import ai_background, dynamic_edit


def run_ad_pipeline(
    image_bytes: bytes,
    filename: str,
    user_caption: str,
) -> tuple[bytes, str]:
    """
    Segment → Claude (caption) → Photoroom v2/edit (AI background).

    Returns (final_image_bytes, marketing_copy). Final image may be the cutout
    if Photoroom edit returns 402/403 (see photoroom_edit_client fallback).
    """
    cutout = remove_background(image_bytes, filename=filename)
    bg_prompt, marketing_copy = parse_caption(user_caption)
    final = ai_background(
        cutout,
        bg_prompt,
        filename="cutout.png",
    )
    return final, marketing_copy


def run_dynamic_image_edit_pipeline(
    image_bytes: bytes,
    filename: str,
    user_instruction: str,
) -> tuple[bytes, str | None]:
    """
    Dynamic /edit flow: Claude → strict JSON → Photoroom v2/edit.

    Optionally segments first when the model sets segment_first (explicit cutout
    request). Returns (image bytes, optional user_message for Telegram caption).
    """
    form_data, segment_first, user_message = parse_dynamic_edit_intent(user_instruction)
    work_bytes = image_bytes
    work_name = filename
    if segment_first:
        work_bytes = remove_background(image_bytes, filename=filename)
        work_name = "cutout.png"
    final = dynamic_edit(work_bytes, work_name, form_data)
    return final, user_message
