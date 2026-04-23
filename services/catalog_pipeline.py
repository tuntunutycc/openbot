from services.anthropic_pipeline import AnthropicPipelineError, parse_caption
from services.catalog_styles import select_catalog_style
from services.photoroom_client import remove_background
from services.photoroom_edit_client import render_catalog_layout


def run_catalog_pipeline(
    image_bytes: bytes,
    filename: str,
    user_instruction: str,
) -> tuple[bytes, str | None]:
    """
    Build a catalog-style image from product input.

    Returns (catalog_image_bytes, optional_marketing_copy).
    """
    style = select_catalog_style(user_instruction)
    cutout = remove_background(image_bytes, filename=filename)

    background_prompt = ""
    marketing_copy: str | None = None
    instruction = (user_instruction or "").strip()
    if instruction:
        try:
            background_prompt, marketing_copy = parse_caption(instruction)
        except AnthropicPipelineError:
            # Catalog rendering should continue even if text generation fails.
            background_prompt = style.default_background_prompt
            marketing_copy = None

    catalog_image = render_catalog_layout(
        cutout,
        style,
        filename="catalog_cutout.png",
        background_prompt=background_prompt,
    )
    return catalog_image, marketing_copy
