# Requirement — Dynamic Image Editing (`dynamic_image_editing`)

## Objective

Let users send a **photo with a natural-language caption** that describes how the image should be edited. The bot does **not** ask the LLM to modify pixels. The LLM acts as an **intent → parameter** mapper: it returns a **strict JSON object** that maps 1:1 to Photoroom **Image Editing API v2** (`POST …/v2/edit`) fields. The bot then calls Photoroom with the user’s image and those parameters and returns the edited result on Telegram.

This feature complements the existing “full ad pipeline” (`run_ad_pipeline`: segment → fixed Claude fields → AI background) and catalog flows by supporting **richer, API-aligned edit instructions** (e.g. output size, padding, solid vs AI background, lighting/shadow modes) driven by user language.

## Trigger and routing (disambiguation)

Today, a **photo or image document with any non-catalog caption** is handled by `run_ad_pipeline`. To avoid breaking that behavior, **dynamic image editing** is activated only when the caption matches a **dedicated pattern**, analogous to `/catalog` / `catalog:`:

- **Command:** `/edit …` (instruction after the command), and/or  
- **Prefix:** `edit: …` (case-insensitive prefix on the caption).

Examples (after stripping the trigger):

- `put this on a wooden table with natural sunlight`
- `remove the background and make it 1080x1080`

Captions that do **not** use this trigger continue to use existing handlers (`run_ad_pipeline`, catalog, plain echo, etc.).

## Inputs

- Telegram message with **photo** or **image document** and a caption that matches the trigger above.
- **Instruction text:** the caption with `/edit` or `edit:` removed and trimmed; must be non-empty after trim (otherwise bot replies with short usage help).
- **Image bytes + filename** from Telegram (same size limits and download behavior as today).
- **Environment:** `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`, `PHOTOROOM_API_KEY` (and optional existing vars: `ANTHROPIC_MODEL`, `PHOTOROOM_EDIT_URL`, `PHOTOROOM_AI_MODEL_VERSION`), via `os.getenv` only.

## Outputs

- **Success:** edited image sent to the user (same delivery patterns as other image replies: photo with optional caption, document fallback, caption length limits).
- **Failure:** short, actionable user-visible message; process must not crash. Use existing exception types where applicable: `AnthropicPipelineError`, `PhotoroomError`.

## LLM role (strict JSON)

- **Single responsibility:** From the user’s natural-language instruction (and minimal fixed context, e.g. “product photo for e-commerce edit”), produce **one JSON object** that the backend can validate and translate into Photoroom `multipart` form fields.
- **No image understanding in the LLM:** The model does not receive the image bytes; it only reasons over text. (If we later add vision, that would be a separate spec revision.)
- **Schema:** Keys and allowed values must align with **Photoroom v2/edit** parameters supported by this project (see `plan.md` for the canonical field list derived from current `photoroom_edit_client` usage and official docs). The JSON must be parseable without ambiguity (no markdown outside optional fenced block handling consistent with `anthropic_pipeline` patterns).
- **Optional human text:** The JSON may include an optional key (e.g. `user_message`) for a short line to show as Telegram caption; if absent or too long, omit or split per existing `_reply_image_with_optional_text` behavior.

## Execution (Photoroom)

- Orchestration lives in **`services/pipeline_orchestrator`** (new entrypoint, e.g. `run_dynamic_image_edit_pipeline`), which:
  1. Calls the new Anthropic-backed parser (see below).
  2. Builds the Photoroom request from validated JSON.
  3. Invokes **`services/photoroom_edit_client`** (extended or new thin wrapper) to POST to v2/edit.
- **Image bytes sent to Photoroom:** The spec requires that the **user’s uploaded image** (as downloaded from Telegram) is what we send as `imageFile`, unless `plan.md` documents a **mandatory** pre-step (e.g. segment-only) required for API correctness or product quality—in which case the requirement is “user’s visual intent applied to their upload” with the documented intermediate noted in the plan.

## Orchestration and “OpenClaw”

- **Initial implementation:** Anthropic is called from **`services/anthropic_pipeline.py`** (new function, e.g. `parse_dynamic_edit_intent`), reusing existing client setup, model selection, JSON extraction helpers, and **mock/fallback policy** patterns where appropriate for non-fatal API degradation.
- **OpenClaw:** The mission positions OpenClaw as the long-term orchestrator. For this phase, **OpenClaw does not need to invoke this path** unless we explicitly add routing later; the requirement is **architectural consistency** (orchestrator module + Anthropic module + Photoroom client), not a hard dependency on `run_openclaw_agent`.

## Error handling and fallbacks

- **Invalid or non-parseable JSON from the model:** Do not call Photoroom with guessed parameters. Respond with a clear message; optional **one retry** with a stricter system prompt is allowed if documented in `plan.md`.
- **Valid JSON but invalid enum/range for Photoroom:** Reject with user-safe message; log detail without secrets.
- **Anthropic API failures:** Follow existing `anthropic_pipeline` conventions (user-visible vs mock vs retry)—with the constraint that mock output, if used, must still be **valid structured edit parameters** or the pipeline must decline with a message (no invalid Photoroom calls).
- **Photoroom errors:** Use `PhotoroomError` and existing quota behavior (e.g. 402/403 fallback) as today unless this feature requires different semantics (document in plan if changed).

## Temporary files and resources

- Prefer **in-memory** buffers (`BytesIO`) for Telegram and HTTP multipart, consistent with the rest of the bot.
- If any temporary filesystem objects are introduced, they must be **removed or closed** in a `finally` path so leaks do not occur under errors.

## Constraints

- No hardcoded API keys.
- Do not remove or silently change `/catalog`, `catalog:`, or the default caption → `run_ad_pipeline` path for non-`edit` captions.
- Changelog entry and branch workflow per `.cursorrules` after implementation approval.

## Out of scope (unless added later)

- LLM vision over the image.
- Routing dynamic edits through `run_openclaw_agent` without a follow-up spec.
- New Telegram commands beyond `/edit` / `edit:` unless explicitly extended in plan.
