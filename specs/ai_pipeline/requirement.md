# Requirement — AI Automation Pipeline (Phase 4 & 5)

## Objective
Deliver an end-to-end Telegram flow where the user sends **one product photo** plus a **short text instruction** (as the photo **caption**), and the bot returns:

1. **Final composite image** — subject from the photo placed on an **AI-generated background** that matches the user’s intent.
2. **Marketing copy** — concise ad/catalog text derived from the same user instruction and the visual context.

This feature combines **Anthropic Claude 3.5** (intent parsing and copy) with **Photoroom** (background removal + generative background via the **Image Editing API**), aligned with the project mission and OpenClaw as the long-term orchestration layer.

## User story
- User uploads a photo in Telegram and sets the caption to something like: *“Make this an ad with a beach background”*.
- Bot acknowledges processing (optional short status) and returns the final image plus marketing text in the same chat thread.

## Business logic (high level)
1. **Ingest:** Receive Telegram message with `photo` (or supported image `document`) **and** non-empty `caption` (user prompt). If caption is missing, reply with usage guidance (do not call paid APIs).
2. **Download:** Fetch image bytes from Telegram (reuse Phase 3 patterns: size limits, MIME checks where applicable).
3. **Cut-out:** Call Photoroom **Remove Background** (`POST https://sdk.photoroom.com/v1/segment`) to produce a **cut-out** (RGBA PNG recommended) of the subject.
4. **Parse intent (LLM):** Send the **user caption** (and minimal metadata, e.g. “product photo”) to **Anthropic Claude 3.5 Sonnet** and require a **structured response** with exactly:
   - `photoroom_background_prompt` — a single detailed English prompt suitable for Photoroom’s `background.prompt` (scene/lighting/style for the new background, not instructions about the API).
   - `marketing_copy` — short marketing text (headline + body or single paragraph per conventions we fix in implementation).
5. **Composite:** Call Photoroom **Image Editing API** generative background — **`POST https://image-api.photoroom.com/v2/edit`** — with:
   - `imageFile` = **cut-out** image from step 3,
   - `referenceBox` = `originalImage` (per Photoroom AI Backgrounds docs),
   - `background.prompt` = `photoroom_background_prompt` from step 4,
   - optional parameters later (`background.negativePrompt`, `background.seed`, model header `pr-ai-background-model-version`, export format/size).
6. **Deliver:** Send the **final edited image** to the user and **the marketing copy** as text (single message with media + caption if length allows, or image then text — decision in `plan.md`).
7. **Errors:** Any step failure yields a **clear user message**; no secret leakage; bot process remains stable.

## Inputs
- Telegram: photo + caption (required for pipeline); optional document + caption if we extend parity with Phase 3.
- Environment (existing / to use): `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`, `PHOTOROOM_API_KEY`.
- Optional future: `OPENCLAW_*` / CMDOP keys if orchestration runs through OpenClaw in Phase 5.

## Outputs
- Binary image: final composite from Photoroom `v2/edit`.
- Text: `marketing_copy` from Claude (and optionally echo/summary of the background prompt for debugging — default off for end users).

## Constraints
- **No hardcoded API keys**; only `os.getenv()` / `.env`.
- **Caption required** for pipeline messages to avoid accidental API spend on bare photos.
- Respect **Photoroom plan limits**: Remove Background (Basic) vs **Image Editing / AI Backgrounds (Plus)** — document assumption that `v2/edit` with `background.prompt` is enabled for the project key.
- **Cost awareness:** order of calls is segment → Claude → `v2/edit`; fail fast on validation errors.
- Preserve existing behaviors: Phase 3 “photo only” background removal, `/start`, text echo, `/agent` stub — **unless** explicitly superseded by a single unified handler (to be decided in `plan.md` to avoid duplicate handlers).

## References (external)
- Photoroom AI Backgrounds (Image Editing API): https://docs.photoroom.com/image-editing-api-plus-plan/ai-backgrounds  
- Photoroom Remove Background (existing Phase 3): https://docs.photoroom.com/remove-background-api  
