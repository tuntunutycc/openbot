# Validation — Dynamic Image Editing (`dynamic_image_editing`)

## Prerequisites

- `.env` configured with valid `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`, `PHOTOROOM_API_KEY` (or deliberate use of mock Anthropic path for degraded testing).
- Bot running locally with one instance polling (avoid 409 conflicts).

## Regression (existing behavior must hold)

1. **Photo, no caption:** Still **background removal only** (Phase 3 path); no new Anthropic call for edit JSON.
2. **Photo + generic caption** (no `edit:`, no `/edit`, no catalog): Still **`run_ad_pipeline`** (segment + `parse_caption` + `ai_background`).
3. **Photo + `catalog:` / `/catalog`:** Unchanged catalog batch behavior.
4. **`/start`:** Includes new lines for dynamic edit; OpenClaw status line still present.
5. **`/agent` / `agent:`:** Unchanged stub or future OpenClaw behavior; no dependency on dynamic edit.

## Functional tests — dynamic edit path

### A. Trigger parsing

| Step | Action | Expected |
|------|--------|----------|
| A1 | Send photo with caption `edit: put the product on a wooden table with natural light` | Dynamic pipeline runs; edited or fallback image returned |
| A2 | Send photo with caption `/edit same instruction` | Same as A1 |
| A3 | Send photo with caption `edit:` only (empty instruction) | Friendly usage error, no Photoroom call |
| A4 | Send photo with caption `Edit: mixed case prefix` | Recognized if spec defines case-insensitive `edit:` |

### B. LLM JSON and Photoroom integration

| Step | Action | Expected |
|------|--------|----------|
| B1 | Instruction explicitly requesting **1080x1080** output | Response image dimensions or metadata consistent with `outputSize` mapping (verify via logs or downstream file inspection if needed) |
| B2 | Instruction: **solid color background** vs **AI scene** | Correct branch: `background.color` vs `background.prompt` in mapped form (spot-check logs in dev with safe logging of **keys only**, not secrets) |
| B3 | Instruction ambiguous or model returns **invalid JSON** | User sees clear error; **no** unhandled exception; optional single retry if implemented |

### C. Anthropic failure modes

| Step | Action | Expected |
|------|--------|----------|
| C1 | Invalid API key (temporary misconfiguration in dev) | User-visible error consistent with `anthropic_pipeline` policy; invalid key should **not** silently mock if current code treats that as fatal |
| C2 | Mock / credit path (if enabled) | Either safe mock JSON path completes E2E or explicit decline per requirement |

### D. Photoroom failure modes

| Step | Action | Expected |
|------|--------|----------|
| D1 | Quota / 402 / 403 (if testable) | Same **fallback** behavior as existing `ai_background` / catalog (e.g. return original/cutoff bytes with warning log)—unless plan explicitly changes this |
| D2 | Bad parameters after validation slip | `PhotoroomError` surfaced; bot does not crash |

### E. Telegram delivery

| Step | Action | Expected |
|------|--------|----------|
| E1 | Short optional `user_message` from JSON | Shown as caption when under Telegram limits |
| E2 | Long `user_message` | Image still sent; text split per `_reply_image_with_optional_text` behavior |

### F. Documents

| Step | Action | Expected |
|------|--------|----------|
| F1 | Image **document** + `edit: …` | Same pipeline as compressed photo |

## Non-functional

- **Memory / temp files:** Run several edits in a row; no growth of stray files in project temp dirs (if any file-based spooling is added later, re-run this check).
- **Logging:** No API keys or full image blobs in logs; at most truncated error bodies per existing patterns.

## Definition of done

- All **Regression** checks pass.
- **A–F** pass on a real Telegram chat against staging or local bot.
- `changelog.md` updated.
- Code review confirms: catalog → dynamic edit → ad pipeline order in `bot.py`, and specs in this folder match implemented JSON schema and mapper.
