# Changelog

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
