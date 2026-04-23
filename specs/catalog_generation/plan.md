# Plan - Catalog Generation (Phase 6)

## Technical Approach
1. Add a dedicated catalog orchestration layer that consumes a product image (and optional instruction text) and outputs a final catalog layout image.
2. Reuse existing utilities:
   - Telegram file download and validation from `bot.py`
   - Subject cutout path from `services/photoroom_client.py`
   - Optional copy generation from `services/anthropic_pipeline.py`
3. Build style-driven rendering profiles (e.g., minimal, premium, lifestyle) that control:
   - background strategy (solid color, generated scene, branded look)
   - subject positioning (center/left/right with margin/padding presets)
   - visual polish (shadow, relight, outline, output size)
4. Produce final catalog image through Photoroom Image Editing API (`/v2/edit`) and, where needed, a lightweight post-process layer for text overlays/template assembly.

## Suggested Modules
- `services/catalog_pipeline.py`
  - entrypoint: `run_catalog_pipeline(image_bytes, filename, user_instruction) -> tuple[bytes, str | None]`
- `services/catalog_styles.py`
  - style preset definitions and mapping logic
- `services/photoroom_edit_client.py` (extend)
  - additional helpers for catalog-oriented edit parameters
- `services/text_overlay.py` (optional)
  - local overlay helper if Photoroom endpoint does not provide required text layout controls

## Telegram Routing Plan
- New trigger strategy for Phase 6:
  - photo/document + instruction keyword or command (e.g., `/catalog`) routes to catalog pipeline
  - existing behavior remains:
    - no caption/photo path for Phase 3 background removal
    - ad pipeline caption path for Phase 4/5
- Response pattern:
  - send final catalog image
  - optionally include generated copy in caption if short; otherwise follow-up text message

## Photoroom Usage Strategy
- Base composition through `POST https://image-api.photoroom.com/v2/edit`
- Candidate parameters:
  - `removeBackground=true` (or provide cutout directly)
  - `background.color` or `background.prompt`
  - `padding`, `margin`, `outputSize`, `shadow.mode`, `lighting.mode`
- Template direction:
  - Prefer Photoroom templating mode if account/plan supports it
  - Otherwise emulate template behavior via deterministic style presets + optional local text overlay

## Fallback/Resilience
- If Photoroom edit call fails with quota/billing errors:
  - return best available fallback image (cutout or pre-edit composition)
  - keep pipeline responsive and user-facing messaging clear
- If Anthropic copy generation fails:
  - return catalog image without copy or use default mock copy based on existing fallback policy

## Non-Goals
- No multi-page catalog documents in this phase
- No persistent campaign/project storage
- No bulk asynchronous batch rendering API yet
