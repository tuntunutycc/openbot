from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from services.anthropic_pipeline import (
    AnthropicPipelineError,
    parse_caption,
    parse_catalog_request_intent,
    parse_catalog_variation_prompts,
)
from services.catalog_styles import get_catalog_style_by_name, select_catalog_style
from services.photoroom_client import PhotoroomError, remove_background
from services.photoroom_edit_client import (
    render_catalog_layout,
    render_catalog_layout_with_fallback_flag,
)

CATALOG_BATCH_SEEDS = [117879368, 55994449, 48672244, 65080068, 999999]


def route_catalog_request(user_instruction: str) -> dict[str, object]:
    """
    Return routed catalog intent with normalized keys:
    {
      "action": "catalog_single"|"catalog_batch",
      "count": int,
      "base_prompt": str,
      "background_prompts": list[str],
    }
    """
    routed = parse_catalog_request_intent(user_instruction)
    action = str(routed.get("action", "catalog_single"))
    count_raw = routed.get("count", 1)
    base_prompt_raw = routed.get("base_prompt", user_instruction)
    prompts_raw = routed.get("background_prompts", [])

    try:
        count = int(count_raw)
    except (ValueError, TypeError):
        count = 1
    count = max(1, min(count, 5))
    if action != "catalog_batch":
        action = "catalog_single"
        count = 1

    base_prompt = str(base_prompt_raw or "").strip() or (user_instruction or "").strip()
    if not base_prompt:
        base_prompt = "Create a clean premium product catalog layout."

    prompts: list[str] = []
    if isinstance(prompts_raw, list):
        for item in prompts_raw:
            if isinstance(item, str) and item.strip():
                prompts.append(item.strip())
    if action == "catalog_batch":
        prompts = prompts[:count]
    else:
        prompts = []

    return {
        "action": action,
        "count": count,
        "base_prompt": base_prompt,
        "background_prompts": prompts,
    }


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


@dataclass
class CatalogBatchResult:
    images: list[bytes]
    marketing_copy: str | None
    full_fallback: bool
    partial_fallback: bool
    all_failed: bool


def run_catalog_batch_pipeline(
    image_bytes: bytes,
    filename: str,
    user_instruction: str,
) -> CatalogBatchResult:
    """
    Generate 3 catalog variations.

    - Runs Photoroom calls concurrently (Option A).
    - Partial fallback: failed/blocked variants are replaced by cutout.
    - Full fallback: if no variant succeeds, return a single cutout image.
    """
    cutout = remove_background(image_bytes, filename=filename)
    instruction = (user_instruction or "").strip()

    marketing_copy: str | None = None
    if instruction:
        try:
            _, marketing_copy = parse_caption(instruction)
        except AnthropicPipelineError:
            marketing_copy = None

    variations = parse_catalog_variation_prompts(instruction)

    def _worker(entry: dict[str, str]) -> tuple[bytes | None, bool, bool]:
        style = get_catalog_style_by_name(entry.get("style_name", "premium"))
        prompt = entry.get("background_prompt", "")
        try:
            out, used_fallback = render_catalog_layout_with_fallback_flag(
                cutout,
                style,
                filename="catalog_cutout.png",
                background_prompt=prompt,
            )
            return out, used_fallback, False
        except PhotoroomError:
            return cutout, True, True

    results: list[tuple[bytes | None, bool, bool]] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(_worker, item) for item in variations]
        for fut in futures:
            results.append(fut.result())

    images: list[bytes] = []
    fallback_count = 0
    hard_fail_count = 0
    for img, used_fallback, hard_fail in results:
        if img is None:
            hard_fail_count += 1
            continue
        images.append(img)
        if used_fallback:
            fallback_count += 1
        if hard_fail:
            hard_fail_count += 1

    if len(images) == 0 or fallback_count == len(results):
        return CatalogBatchResult(
            images=[cutout],
            marketing_copy=marketing_copy,
            full_fallback=True,
            partial_fallback=False,
            all_failed=True,
        )

    partial = fallback_count > 0 or hard_fail_count > 0 or len(images) < 3
    if len(images) > 3:
        images = images[:3]

    return CatalogBatchResult(
        images=images,
        marketing_copy=marketing_copy,
        full_fallback=False,
        partial_fallback=partial,
        all_failed=False,
    )


def run_catalog_batch_n_pipeline(
    image_bytes: bytes,
    filename: str,
    user_instruction: str,
    count: int,
    background_prompts: list[str] | None = None,
) -> list[bytes]:
    """
    Generate N catalog variations sequentially (N is clamped to 1..5).

    Uses LLM-supplied diverse prompts when available; otherwise falls back to
    per-iteration prompt generation from base instruction.
    """
    n = max(1, min(count, 5))
    cutout = remove_background(image_bytes, filename=filename)
    base_instruction = (user_instruction or "").strip() or "Create a clean premium product catalog layout."
    style = select_catalog_style(base_instruction)
    prompts = [p.strip() for p in (background_prompts or []) if isinstance(p, str) and p.strip()]
    if len(prompts) < n:
        prompts = []

    images: list[bytes] = []
    for idx in range(1, n + 1):
        seed = CATALOG_BATCH_SEEDS[idx - 1]
        if prompts:
            background_prompt = prompts[idx - 1]
        else:
            loop_instruction = f"{base_instruction} Variation {idx}"
            try:
                background_prompt, _ = parse_caption(loop_instruction)
            except AnthropicPipelineError:
                background_prompt = style.default_background_prompt

        try:
            out, _ = render_catalog_layout_with_fallback_flag(
                cutout,
                style,
                filename="catalog_cutout.png",
                background_prompt=background_prompt,
                background_seed=seed,
                include_output_size=False,
            )
            images.append(out)
        except PhotoroomError:
            # Keep the sequence flowing even if one iteration fails.
            images.append(cutout)

    return images
