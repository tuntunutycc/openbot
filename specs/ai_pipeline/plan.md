# Plan — AI Automation Pipeline (Phase 4 & 5)

## Scope split
- **Phase 4 (this repo milestone):** Anthropic integration — parse user caption → structured `photoroom_background_prompt` + `marketing_copy`; unit-level validation and dry-run safeguards.
- **Phase 5:** End-to-end assembly in the Telegram bot — segment → Claude → Photoroom `v2/edit` → reply; optional OpenClaw orchestration hook so the same steps can be triggered via `run_openclaw_agent` later without duplicating business logic.

## Telegram UX
- **Trigger:** Message with `content_types=['photo']` **and** `message.caption` stripped non-empty. (Optional extension: image `document` + caption with same rules.)
- **Missing caption:** Reply with help text, e.g. *“Send a photo and put your instructions in the caption (e.g. beach background ad).”* — **no** Anthropic/Photoroom generative calls.
- **Collision with Phase 3:** Today, a photo **without** caption triggers Remove Background only. A photo **with** caption triggers the **pipeline** (segment + Claude + `v2/edit`). Document this precedence in `bot.py` handler order and comments.
- **Reply format:** Prefer `send_photo` with the final image and put `marketing_copy` in **`caption`** if under Telegram caption limits; if copy is too long, send photo then a follow-up `reply_to` text message.

## Anthropic (Claude 3.5 Sonnet)
- **Module:** `services/anthropic_pipeline.py` (name flexible) responsible for:
  - Reading `ANTHROPIC_API_KEY` from the environment.
  - Calling the **Messages API** with model **Claude 3.5 Sonnet** (exact model ID pinned in code constants, e.g. `claude-3-5-sonnet-20241022`, updated when we bump versions).
  - **Structured output:** System + user prompt that requires **valid JSON only** (no markdown fence) with keys:
    - `photoroom_background_prompt` (string)
    - `marketing_copy` (string)
  - Validation: parse JSON; on failure retry once with a “fix to valid JSON only” nudge or fall back to user-visible error.
- **OpenClaw:** Phase 5 may invoke this module from `services/openclaw_agent.py` or a thin `services/pipeline_orchestrator.py` so `/agent` and caption-pipeline share logic. Phase 4 can implement the Anthropic module **without** requiring CMDOP connectivity.

**Dependency:** add official `anthropic` Python SDK to `requirements.txt` (preferred over raw HTTP for maintainability), unless we standardize on `httpx` only — pick SDK in implementation and record in changelog.

## Photoroom — two-step image flow
1. **Cut-out (existing):** Reuse `services/photoroom_client.py` (`remove_background` / segment) to obtain **RGBA PNG** bytes from the **original** Telegram image.
2. **Generative composite:** New client helper, e.g. `services/photoroom_edit_client.py`:
   - `POST https://image-api.photoroom.com/v2/edit`
   - Headers: `x-api-key: <PHOTOROOM_API_KEY>`
   - Optional: `pr-ai-background-model-version` header per docs (e.g. default model `3` or Studio beta identifier when we want a specific look).
   - Multipart form fields (per [AI Backgrounds](https://docs.photoroom.com/image-editing-api-plus-plan/ai-backgrounds)):
     - `imageFile` → cut-out bytes (filename e.g. `cutout.png`)
     - `referenceBox` → `originalImage`
     - `background.prompt` → Claude output `photoroom_background_prompt`
   - Response: binary image (default PNG); handle errors similarly to segment client (JSON `detail` when present).
   - **Plan assumption:** API key has **Image Editing / Plus** access for `background.prompt`. If account is Basic-only, return a clear user message pointing to plan upgrade (map `402` / doc-specific errors).

## Orchestration module (Phase 5)
- **`services/pipeline_orchestrator.py`** (recommended):
  - `run_ad_pipeline(image_bytes: bytes, filename: str, user_caption: str) -> tuple[bytes, str]` returning `(final_image_bytes, marketing_copy)`.
  - Internals: segment → `anthropic_pipeline.parse_caption` → `photoroom_edit_client.ai_background`.
  - Centralize size limits, timeouts, and user-safe error mapping.
- **`bot.py`:** New handler or refactored photo handler: if caption → orchestrator; elif no caption → existing Phase 3 `remove_background` path.

## File structure (target)
- `services/photoroom_client.py` — existing segment API.
- `services/photoroom_edit_client.py` — **new** `v2/edit` AI background call.
- `services/anthropic_pipeline.py` — **new** Claude structured JSON extraction.
- `services/pipeline_orchestrator.py` — **new** Phase 5 glue.
- `bot.py` — caption-aware routing.
- `.env` — already has keys; optional `ANTHROPIC_MODEL`, `PHOTOROOM_AI_MODEL_VERSION` later.
- `requirements.txt` — add `anthropic` (if chosen).
- `changelog.md` — implementation entries after approval.

## Non-goals (for this spec)
- Batch processing, user accounts, or persistence of assets.
- Fine-tuning models or custom Photoroom templates.
- Full OpenClaw remote agent execution **required** for MVP (optional enhancement in Phase 5).
