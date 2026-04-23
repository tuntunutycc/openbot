from services.anthropic_pipeline import AnthropicPipelineError, parse_caption
from services.photoroom_client import PhotoroomError, remove_background
from services.photoroom_edit_client import ai_background


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
