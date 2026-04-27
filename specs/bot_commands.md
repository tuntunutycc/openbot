# OpenBot Commands and Triggers

This quick reference summarizes how Telegram inputs are routed in `bot.py` and which backend pipeline handles each case.

## Command and Trigger Matrix

| Command / Trigger | Input Type | Action / Description | Backend Pipeline |
|---|---|---|---|
| `/start` | Text only | Sends startup/help message with available routes and OpenClaw runtime status. | `handle_start` in `bot.py` (reads `OPENCLAW_HANDLE`) |
| `/agent <message>` | Text only | Sends user request to OpenClaw agent path and replies with routed result/fallback. If message is missing, bot replies with usage text. | `run_openclaw_agent` (`services/openclaw_agent.py`) |
| `agent:<message>` | Text only | Alternate text trigger for OpenClaw routing without slash command. If text after `agent:` is empty, bot prompts user to provide it. | `run_openclaw_agent` (`services/openclaw_agent.py`) |
| `/catalog <instruction>` (caption prefix) | Photo + caption **or** Image document + caption | Routes intent via Anthropic. If instruction implies batch (including Burmese requests like `မတူညီတဲ့ ပုံငါးပုံ ထုတ်ပေး`), Claude returns a diverse `background_prompts` list and bot runs seeded batch generation from those prompts; otherwise standard catalog variation flow. | `route_catalog_request` + (`run_catalog_batch_n_pipeline` or `run_catalog_batch_pipeline`) |
| `catalog:<instruction>` (caption prefix) | Photo + caption **or** Image document + caption | Same routed catalog behavior as `/catalog` with prefix style trigger. | `route_catalog_request` + (`run_catalog_batch_n_pipeline` or `run_catalog_batch_pipeline`) |
| `catalog batch N: <instruction>` (caption prefix) | Photo + caption **or** Image document + caption | Sequentially generates up to `N` catalog variations (hard-capped at 5), reusing the same downloaded source image/cutout; each loop appends `Variation X`, applies a distinct predefined Photoroom `background.seed`, and sends each image back in order with caption `Variation X`. | `run_catalog_batch_n_pipeline` (`services/catalog_pipeline.py`) |
| `/edit <instruction>` (caption prefix) | Photo + caption **or** Image document + caption | Runs dynamic edit flow: LLM extracts v2/edit parameters, mapping/validation applies strict allowlists, then Photoroom v2/edit executes. | `run_dynamic_image_edit_pipeline` (`services/pipeline_orchestrator.py`) -> `parse_dynamic_edit_intent` + `normalize_and_validate_dynamic_edit` + `dynamic_edit` |
| `edit:<instruction>` (caption prefix) | Photo + caption **or** Image document + caption | Same dynamic edit flow as `/edit`, using prefix style trigger. | `run_dynamic_image_edit_pipeline` (`services/pipeline_orchestrator.py`) |
| Any other non-empty caption (not catalog/edit) | Photo + caption **or** Image document + caption | Runs ad pipeline: remove background, parse caption via Anthropic, apply AI background edit, then return image + copy. | `run_ad_pipeline` (`services/pipeline_orchestrator.py`) |
| No caption | Photo only **or** Image document only | Background removal only (Phase 3 behavior). | `_process_and_reply_image` -> `remove_background` (`services/photoroom_client.py`) |
| Any other text (no command/prefix match) | Text only | Echoes text back to user (default fallback). | `handle_echo` in `bot.py` |

## Routing Priority for Images with Captions

For both `photo` and image `document` handlers, the caption routing order is:

1. Catalog batch trigger (`catalog batch N:`)
2. Catalog trigger (`/catalog` or `catalog:`)
3. Dynamic edit trigger (`/edit` or `edit:`)
4. Default ad pipeline (`run_ad_pipeline`)

If there is no caption, the bot uses background-removal-only flow.

## Input Constraints and Notes

- Image size limit: `MAX_IMAGE_BYTES = 20 MB` (guarded in both photo/document handlers).
- Caption length handling: image responses use `_reply_image_with_optional_text` and respect Telegram caption limits.
- Dynamic edit enum safety: invalid `lighting_mode` and `shadow_mode` values are filtered out before calling Photoroom.
- Catalog batch count is clamped to `1..5` for API safety.
- `catalog batch` must follow this format exactly: `catalog batch N: <instruction>`. If the format is invalid, it falls through to normal caption routing.
- Catalog and dynamic-edit triggers work only when included in the image caption (photo/document), not as plain text messages.
- Seeded diversity for catalog batch: each batch item uses a distinct predefined Photoroom `background.seed` to avoid identical outputs on restrictive prompts.

## Quick Usage Examples

- `/start`
- `/agent summarize today tasks`
- `agent: check openclaw status`
- `catalog: clean premium product catalog layout`
- `catalog batch 5: modern studio backdrop with soft shadows`
- `/edit remove background and keep realistic relight`
- `edit: put this on a wooden table with natural daylight`
