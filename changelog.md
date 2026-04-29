# Changelog

## 2026-04-29 (spec-roadmap-changelog sync)
- Performed a three-way sync between `specs/`, `roadmap.md`, and `changelog.md`.
- Updated `specs/roadmap.md` and added root `roadmap.md` so feature milestones now mirror `specs/<feature_name>/` folder names exactly.
- Aligned roadmap statuses with changelog implementation history: `openclaw_init`, `photoroom_api`, `ai_pipeline`, `catalog_generation`, `batch_variations`, `custom_prompts`, and `dynamic_image_editing` are marked Done.
- No spec folder rename was applied because no unambiguous folder-name conflict was found; legacy phase-style labels are preserved in changelog entries for traceability.

## 2026-04-27 (catalog intent router + seeded batch diversity)
- Added catalog intent routing in `services/anthropic_pipeline.py` (`parse_catalog_request_intent`) with JSON output (`action`, `count`, `base_prompt`) to detect natural-language batch requests in Burmese/English and clamp count to max 5.
- Added `route_catalog_request` in `services/catalog_pipeline.py`; `/catalog ...` and `catalog: ...` now auto-switch to batch mode when routed action is `catalog_batch`.
- Strengthened batch distinctness: `run_catalog_batch_n_pipeline` now applies fixed Photoroom seeds `[117879368, 55994449, 48672244, 65080068, 999999]` per iteration through `background.seed`.
- Extended mapping layer (`services/dynamic_edit_mapping.py`) to accept integer `seed`/`background_seed` and map to `background.seed` safely.
- Refined catalog batch creativity: router now returns `background_prompts` for batch mode, and `run_catalog_batch_n_pipeline` iterates those LLM-provided prompts directly (falling back to generated prompts only when missing). Batch captions can include the prompt description per variation.
- Prompt quality uplift: `CATALOG_ROUTER_SYSTEM` now instructs Claude to generate high-end commercial photography prompts (cinematic studio lighting, bokeh, depth of field, photorealistic textures, 8k detail, color grading, camera-style details).
- Blending hardening: mapping now enforces default `lighting.mode=ai.auto` and `shadow.mode=ai.soft` when omitted; catalog v2/edit payload path keeps the same baseline blending defaults.

## 2026-04-27 (catalog batch N trigger)
- Added `catalog batch N: <prompt>` caption trigger in `bot.py` (photo + image document paths), with hard cap `N <= 5`.
- Implemented sequential batch generation in `services/catalog_pipeline.py` via `run_catalog_batch_n_pipeline`: reuses the same downloaded source image/cutout, appends `Variation X` to the instruction each loop, and returns images in order for sequential send-back.
- Updated `services/photoroom_edit_client.py` `render_catalog_layout_with_fallback_flag(..., include_output_size=False)` path so catalog batch keeps original dimensions by omitting `outputSize`.
- Added seeded diversity to batch-N catalog: `run_catalog_batch_n_pipeline` now applies predefined Photoroom seeds `[117879368, 55994449, 48672244, 65080068, 999999]` per iteration through `background.seed` in catalog v2/edit payload.
- Updated `specs/bot_commands.md` quick reference with the new trigger and routing priority.

## 2026-04-27 (dynamic edit enum hardening)
- Dynamic edit: `DYNAMIC_EDIT_SYSTEM` lists allowed `shadow_mode` values; `lighting_mode` only `ai.auto` or `ai.preserve-hue-and-saturation`, omit when unsure; explicitly forbids `ai.studio`, `ai.environment`, `ai.natural`, `none`, etc.
- `dynamic_edit_mapping`: `_apply_shadow_mode_filter` / `_apply_lighting_mode_filter` only add `shadow.mode` / `lighting.mode` when the LLM string is in the Python allowlist; otherwise the key is omitted (no invalid strings sent to Photoroom).

## 2026-04-27 (dynamic image editing)
- Implemented Feature-Based SDD `specs/dynamic_image_editing/`: **`/edit …`** or **`edit: …`** on a photo or image document runs `run_dynamic_image_edit_pipeline` (catalog and plain captioned photos unchanged).
- Added `services/dynamic_edit_mapping.py` to validate Claude JSON and map snake_case fields to Photoroom v2/edit multipart keys (`background.prompt`, `shadow.mode`, `outputSize`, etc.).
- Extended `services/anthropic_pipeline.py` with `DYNAMIC_EDIT_SYSTEM`, `parse_dynamic_edit_intent`, and mock payload parity with existing Anthropic fallback behavior.
- Refactored `services/photoroom_edit_client.py` with shared `_post_v2_edit` plus new `dynamic_edit()`; `ai_background` now delegates to the same POST helper (402/403 still return input image bytes).
- `services/pipeline_orchestrator.py`: new `run_dynamic_image_edit_pipeline` (optional `segment_first` cutout via existing `remove_background` before v2/edit).
- `bot.py`: `_is_dynamic_edit_instruction` / `_extract_dynamic_edit_instruction`, wired in photo and document handlers after catalog; `/start` help text updated.

## 2026-04-27
- `bot.py`: call `load_dotenv(override=True)` immediately after importing `dotenv` so each process run picks up the latest `.env` values; keep `TELEGRAM_BOT_TOKEN` from `os.getenv`.
- Added startup logging: token prefix (first five characters), `get_me()` username, `remove_webhook()`, and structured log lines before polling; wrapped `infinity_polling()` in try/except with `logger.exception` for clearer connection/API failures.

## 2026-04-22
- Project initialized with Spec-Driven Development (SDD) structure, Cursor rules, and roadmap.
- Phase 1 initialized: added `.gitignore`, created `.env` placeholders, and implemented a minimal Telegram bot (`bot.py`) with `/start` and text echo handlers using `pyTelegramBotAPI` and `python-dotenv`.
- Added `requirements.txt` with core dependencies (`pyTelegramBotAPI`, `python-dotenv`, `requests`) and installed them into the local `.venv`.
- Confirmed manually generated `requirements.txt` (via `pip freeze`) is included on `feature/phase2-openclaw-init` to support dependency tracking for Ubuntu server deployment.
- Added `TELEGRAM_BOT_USERNAME=@photoadsclawbot` to `.env` for explicit bot identity configuration.
- Upgraded SDD workflow with a Feature-Based SDD rule in `.cursorrules`, created branch `feature/phase3-photoroom`, and added Phase 3 Photoroom specs: `specs/photoroom_api/requirement.md`, `specs/photoroom_api/plan.md`, and `specs/photoroom_api/validation.md` for approval before coding.
- Created Phase 2 OpenClaw spec package on branch `feature/phase2-openclaw-specs`: `specs/openclaw_init/requirement.md`, `specs/openclaw_init/plan.md`, and `specs/openclaw_init/validation.md` for approval before implementation.
- Implemented Phase 2 OpenClaw runtime scaffolding: added `services/openclaw_runtime.py` and `services/openclaw_agent.py`, wired `bot.py` with startup initialization, `/agent` command routing, `agent:` text routing, and deterministic fallback behavior when OpenClaw is unavailable.
- Installed `openclaw` in the local `.venv` and added it to `requirements.txt` for Phase 2 dependency completeness.

## 2026-04-23
- Updated `ANTHROPIC_API_KEY` in `.env` (replaced placeholder; value not logged here).
- Updated `PHOTOROOM_API_KEY` in `.env` (replaced placeholder; value not logged here).
- Fixed OpenClaw import path: alias `cmdop.exceptions.TimeoutError` to `ConnectionTimeoutError` before loading `openclaw`, and added explicit `tenacity` dependency for CMDOP generated clients.
- Merged `feature/phase2-openclaw-specs` into `main` (Phase 2 approved) and deleted the feature branch locally.
- Opened `feature/phase3-photoroom-specs` and refreshed Feature-Based SDD specs under `specs/photoroom_api/` (`requirement.md`, `plan.md`, `validation.md`) for Photoroom Remove Background (`POST https://sdk.photoroom.com/v1/segment`); implementation deferred pending explicit spec approval.
- Phase 3 implemented (on `feature/phase3-photoroom-specs`): added `services/photoroom_client.py` (`remove_background`, `PhotoroomError`, JSON/base64 or binary responses, optional `PHOTOROOM_SEGMENT_URL`); extended `bot.py` with photo and image-document handlers, Telegram download + size guard, Photoroom call, and `send_photo` with `send_document` fallback; `/start` text mentions background removal.
- Updated `PHOTOROOM_API_KEY` in `.env` (value not logged here).
- Merged `feature/phase3-photoroom-specs` into `main` after successful Telegram validation; deleted the feature branch locally.
- Opened `feature/phase4-ai-pipeline-specs` and added Feature-Based SDD specs under `specs/ai_pipeline/` (`requirement.md`, `plan.md`, `validation.md`) for the Phase 4/5 AI automation pipeline: caption + photo → Anthropic structured prompt/copy → Photoroom segment + `POST https://image-api.photoroom.com/v2/edit` AI background → Telegram delivery; **no implementation code until explicit spec approval**.
- Phase 4/5 pipeline implemented (on `feature/phase4-ai-pipeline-specs`): added `services/anthropic_pipeline.py` (Claude Messages JSON: `photoroom_background_prompt`, `marketing_copy`), `services/photoroom_edit_client.py` (`POST https://image-api.photoroom.com/v2/edit` with AI background; on **402/403** logs `Photoroom API Quota exceeded, using fallback image.` and returns the cutout), `services/pipeline_orchestrator.py` (`run_ad_pipeline`); `bot.py` routes photo/document **with caption** through the full pipeline and **without caption** through Phase 3 segment-only; reply uses photo caption for short copy or follow-up message; added `anthropic` to `requirements.txt` and `logging.basicConfig` for pipeline warnings.
- Anthropic: default model ID is now `claude-sonnet-4-5` (via `DEFAULT_MODEL` / optional `ANTHROPIC_MODEL` in `.env`) because dated `claude-3-5-sonnet-*` IDs often return HTTP **400**; `BadRequestError` and other `APIError`s are logged and surfaced with API error text.
- Anthropic pipeline fallback: on **credit/billing-style** failures (e.g. “credit balance too low”) or most other Anthropic **API** failures (rate limits, overload, etc.), `parse_caption` logs `Anthropic API credit low, using mock response.` and returns fixed mock `photoroom_background_prompt` / `marketing_copy` for E2E testing; **invalid API key** and **non–credit BadRequest** (e.g. bad model id) still raise to the user.
- Updated `PHOTOROOM_API_KEY` in `.env` (value not logged here).
- Merged `feature/phase4-ai-pipeline-specs` into `main`, deleted the branch locally, and pushed updated `main` to GitHub.
- Opened `feature/phase6-catalog-specs` and added Feature-Based SDD specs under `specs/catalog_generation/` (`requirement.md`, `plan.md`, `validation.md`) for professional catalog image generation; implementation pending explicit approval.
- Phase 6 implemented (on `feature/phase6-catalog-specs`): added `services/catalog_styles.py` (deterministic style presets), `services/catalog_pipeline.py` (`run_catalog_pipeline`), and extended `services/photoroom_edit_client.py` with `render_catalog_layout` for catalog composition via `/v2/edit`.
- `bot.py` now supports catalog routing on image captions prefixed with `/catalog` or `catalog:`; catalog responses return a composed catalog image and optional generated copy while preserving Phase 3 and Phase 4/5 flows.
- Added Phase 6 fallback resilience: when catalog Photoroom composition returns **402/403** quota/billing errors, logs `Photoroom API Quota exceeded, using fallback image.` and returns the cutout image so Telegram/Claude end-to-end testing can continue.
- Updated `PHOTOROOM_API_KEY` in `.env` (switched from sandbox-prefixed value to production-style key; value not logged here).
- Merged `feature/phase6-catalog-specs` into `main` (Phase 6 approved) and deleted the local feature branch.
- Opened `feature/phase7-batch-variations-specs` and added Feature-Based SDD specs under `specs/batch_variations/` (`requirement.md`, `plan.md`, `validation.md`) for `/catalog` multi-variation album generation with quota-safe fallback behavior; implementation pending explicit approval.
- Opened `specs/custom_prompts/` and added Phase 8 specs (`requirement.md`, `plan.md`) for Burmese intent translation + professional English prompt enhancement and strongly distinct 3-way catalog variation prompt generation; implementation pending explicit approval.
- Phase 8 implemented on `feature/phase8-custom-burmese-prompts`: deeply overhauled Anthropic system prompts in `services/anthropic_pipeline.py` with a Master Prompt Engineer persona for Burmese-to-English professional prompt engineering and enhanced single-flow output quality.
- Batch variation prompt generation now enforces strict 3-theme coverage (`minimal`, `lifestyle`, `premium`) with robust JSON-array parsing and explicit prompt distinctness checks to avoid near-duplicate outputs.
- Added stronger correction retry instructions for invalid batch outputs while preserving existing Anthropic mock behavior and leaving all Photoroom quota/billing fallback logic unchanged.
- Phase 8 prompt policy refined for bilingual handling: system prompts now explicitly support both Burmese and English inputs, applying the same Master Prompt Engineer quality rules while dynamically choosing translate+enhance (Burmese) vs direct enhance (English).
- Phase 7 implemented (on `feature/phase7-batch-variations-specs`): `/catalog` now generates 3 design variations using concurrent Photoroom edit requests (Option A) through `run_catalog_batch_pipeline`.
- Added Claude variation prompt generation (`parse_catalog_variation_prompts`) for strict 3-item JSON arrays (`minimal`, `premium`, `lifestyle`) with deterministic defaults when model output is invalid/unavailable.
- Extended catalog rendering with variant-level fallback metadata (`render_catalog_layout_with_fallback_flag`) and kept quota/billing safety: HTTP **402/403** logs `Photoroom API Quota exceeded, using fallback image.` and substitutes cutout safely.
- Telegram delivery now uses album mode (`send_media_group`) for multi-image catalog outputs, with explicit handling for partial fallback (album + note) and full fallback (single mock/cutout image + message), while preserving earlier phase routes.
