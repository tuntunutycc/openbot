from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogStyle:
    name: str
    background_color: str = "FFFFFF"
    padding: str = "0.12"
    margin: str = "0.03"
    shadow_mode: str = "ai.soft"
    lighting_mode: str = "ai.auto"
    output_size: str = "1200x1200"
    scaling: str = "fit"
    use_ai_background: bool = False
    default_background_prompt: str = ""


CATALOG_STYLES: dict[str, CatalogStyle] = {
    "minimal": CatalogStyle(
        name="minimal",
        background_color="FFFFFF",
        padding="0.16",
        margin="0.02",
        shadow_mode="ai.soft",
        lighting_mode="ai.auto",
        output_size="1200x1200",
        scaling="fit",
        use_ai_background=False,
    ),
    "premium": CatalogStyle(
        name="premium",
        background_color="F4F1EC",
        padding="0.14",
        margin="0.03",
        shadow_mode="ai.soft",
        lighting_mode="ai.auto",
        output_size="1200x1200",
        scaling="fit",
        use_ai_background=False,
    ),
    "lifestyle": CatalogStyle(
        name="lifestyle",
        background_color="FFFFFF",
        padding="0.10",
        margin="0.02",
        shadow_mode="ai.soft",
        lighting_mode="ai.auto",
        output_size="1200x1200",
        scaling="fit",
        use_ai_background=True,
        default_background_prompt=(
            "clean lifestyle product catalog setting, soft natural light, "
            "professional commercial photography background"
        ),
    ),
}


def get_catalog_style_by_name(style_name: str) -> CatalogStyle:
    key = (style_name or "").strip().lower()
    if key in CATALOG_STYLES:
        return CATALOG_STYLES[key]
    return CATALOG_STYLES["premium"]


def select_catalog_style(user_instruction: str) -> CatalogStyle:
    text = (user_instruction or "").lower()
    if any(k in text for k in ("minimal", "clean", "simple", "plain")):
        return CATALOG_STYLES["minimal"]
    if any(k in text for k in ("lifestyle", "beach", "summer", "outdoor", "scene")):
        return CATALOG_STYLES["lifestyle"]
    if any(k in text for k in ("premium", "luxury", "gold", "elegant")):
        return CATALOG_STYLES["premium"]
    return CATALOG_STYLES["premium"]
