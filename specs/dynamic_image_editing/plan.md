# Plan — Dynamic Image Editing (`dynamic_image_editing`)

## Overview

Add a **caption-triggered** pipeline: `/edit …` or `edit: …` + image → **Claude** produces **strict JSON** → validate/map to **Photoroom v2/edit** multipart fields → return image via Telegram. Wire through `pipeline_orchestrator`, extend `photoroom_edit_client`, and add Anthropic parsing beside existing `parse_caption` / catalog helpers.

## Canonical Photoroom v2/edit parameter surface (initial)

Base URL and auth already live in `photoroom_edit_client.py` (`DEFAULT_EDIT_URL`, `x-api-key`, optional `pr-ai-background-model-version` header).

Fields **already used** in this repo (must be covered by the LLM JSON schema and mapper):

| Photoroom form key | Used in | Notes |
|--------------------|---------|--------|
| `imageFile` | All | Multipart file; always from pipeline |
| `referenceBox` | `ai_background`, `render_catalog_layout` | Typically `originalImage` |
| `background.prompt` | AI background paths | String |
| `background.color` | Catalog solid background | String (e.g. hex) |
| `padding`, `margin` | Catalog | Strings per API |
| `shadow.mode`, `lighting.mode` | Catalog | Strings per API |
| `outputSize` | Catalog | e.g. `1080x1080` style values |
| `scaling` | Catalog | String per API |

The **LLM JSON schema** should use stable internal names (e.g. snake_case) that a pure-Python function maps to the exact multipart keys (including dotted keys like `background.prompt`). Any additional v2/edit fields allowed by Photoroom docs may be added in a single “extensions” object with explicit allowlisting to avoid arbitrary key injection.

## New / changed modules

### 1. `services/anthropic_pipeline.py`

- Add a dedicated **system prompt** describing the JSON schema, allowed values for enums (shadow/lighting/scaling/outputSize if constrained), and rules: output **only** JSON, no extra keys unless allowlisted, Burmese/English handling consistent with existing persona where useful.
- Add **`parse_dynamic_edit_intent(user_instruction: str) -> dict`** (name flexible) that:
  - Calls Claude with the new system prompt + user instruction.
  - Parses JSON via existing `_extract_json_object` (and fence stripping).
  - Returns a **normalized dict** for the mapper, or raises `AnthropicPipelineError`.
- **Mock / fallback:** Reuse `_should_use_anthropic_mock` / `_call_claude` patterns. If mock is triggered, return a **safe default** JSON (e.g. AI background + neutral table scene + sensible `outputSize`) or raise—**prefer** a documented mock JSON that always passes validation so E2E still works without credits.
- **OpenClaw:** No new OpenClaw import here; keep Anthropic calls in this module for parity with `parse_caption`.

### 2. `services/photoroom_edit_client.py`

- Add **`dynamic_edit(image_bytes, filename, edit_params: dict[str, str], *, ...)`** (signature approximate) that:
  - Accepts **already-flattened** multipart `data` dict (string values only, matching `requests` usage elsewhere).
  - Sets `files={"imageFile": (filename, image_bytes)}`.
  - Reuses the same response handling as `ai_background` (JSON base64 vs raw, 402/403 fallback, `PhotoroomError`).
- Alternatively, factor a small **private** `_post_v2_edit(files, data, headers)` to avoid duplicating the POST/parse block—only if it keeps the diff focused.
- **Conflict resolution:** If both `background.prompt` and `background.color` appear, follow Photoroom semantics (document precedence in code comment); LLM prompt should discourage conflicting combos.

### 3. `services/pipeline_orchestrator.py`

- Add **`run_dynamic_image_edit_pipeline(image_bytes: bytes, filename: str, user_instruction: str) -> tuple[bytes, str | None]`**:
  1. `edit_spec = parse_dynamic_edit_intent(user_instruction)` (or equivalent).
  2. `form_data = map_edit_json_to_photoroom_form(edit_spec)` (new function; could live in `photoroom_edit_client` or a tiny `dynamic_edit_mapping.py` if needed—prefer colocation with Photoroom to keep one import site).
  3. `out_bytes = dynamic_edit(image_bytes, filename, form_data)`.
  4. Return `(out_bytes, optional_caption_from_json)`.

**Image bytes:** Start with **Telegram download as-is** for v2/edit to match the requirement “original image + parameters”. If integration tests show Photoroom quality issues for uncut product photos on AI background, add an **optional** flag in JSON (e.g. `segment_first: true`) or a documented automatic segment step using existing `remove_background`—decide during implementation and record in changelog.

### 4. `bot.py`

- Add helper **`_is_dynamic_edit_instruction(text: str) -> bool`** mirroring `_is_catalog_instruction`: e.g. strip and check `startswith("/edit")` or lower `startswith("edit:")`.
- In **`handle_photo`** and **`handle_image_document`**, **before** catalog check or generic caption `run_ad_pipeline`:
  - If caption matches dynamic-edit trigger, extract instruction (same pattern as catalog: command vs prefix).
  - If instruction empty → reply usage: e.g. “Use `/edit …` or `edit: …` with your instruction.”
  - Else call `run_dynamic_image_edit_pipeline(data, name_or_filename, instruction)`.
  - On `AnthropicPipelineError` / `PhotoroomError`, `reply_to` with `str(exc)` or a generic fallback message (match existing style).
  - On success, reuse **`_reply_image_with_optional_text`** with a sensible `output_name` (e.g. `dynamic_edit.png`).
- **Order of checks** (recommended): catalog → **dynamic edit** → existing `run_ad_pipeline` for remaining captioned images → no caption → background-only.

### 5. `services/openclaw_agent.py` / OpenClaw

- **No change required** for MVP. Optional future: mention in `validation.md` that `/agent` must remain unaffected.

## JSON schema (implementation detail)

Define in code a **single source of truth**: e.g. `TypedDict` or dataclass + `ALLOWED_KEYS`, plus validation function that raises `AnthropicPipelineError` or a dedicated `DynamicEditValidationError` mapped to user text. The spec for the LLM should list:

- Required vs optional keys.
- Mutually exclusive groups (solid color vs AI prompt).
- Default `referenceBox` if omitted (`originalImage`).

Exact schema text will live in the system prompt in `anthropic_pipeline.py` during implementation.

## Temporary files

- Default: **no temp files**; use `BytesIO` for outbound Telegram sends (existing pattern).
- If multipart requires spooling to disk on a future refactor, use `tempfile` + `delete=True` or explicit unlink in `finally`.

## Documentation and ops

- After implementation: update **`changelog.md`** with feature summary and routing behavior.
- Update **`/start`** help text in `bot.py` to mention `/edit` and `edit:`.

## Dependencies

- No new packages expected (`anthropic`, `requests`, `telebot` already present).

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| LLM emits invalid enums | Strict allowlist + validation before Photoroom |
| Overlap with ad pipeline captions | Reserved `edit:` / `/edit` only |
| Raw photo + AI background quality | Document segment optional step if needed |
| Token / caption length | Truncate or omit optional caption per `TELEGRAM_CAPTION_MAX` |
