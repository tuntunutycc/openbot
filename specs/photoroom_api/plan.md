# Plan - Photoroom API Background Removal (Phase 3)

## Technical Approach
1. Add a small **Photoroom client** module that wraps `requests`: build multipart form, send `POST`, return raw image bytes or raise a typed/local exception.
2. Extend **`bot.py`** with message handler(s) for photos and image documents: resolve `file_id`, call `bot.get_file` + download, then call the client.
3. Reply with `bot.send_photo` (or `send_document` if format is not displayable as photo) using `BytesIO` or temp buffer.
4. Centralize user-facing error strings in one place (or thin helpers) so handlers stay small.

## Planned File Structure
- `services/photoroom_client.py` — `remove_background(image_bytes: bytes, filename: str | None, **options) -> bytes` (name flexible); constants for default URL `https://sdk.photoroom.com/v1/segment`.
- `bot.py` — new handlers: e.g. `@bot.message_handler(content_types=['photo'])` and optional `document` path gated by mime type.
- `.env` — `PHOTOROOM_API_KEY` (already present); optional `PHOTOROOM_SEGMENT_URL` defaulting to official segment URL if we want configurability.
- `requirements.txt` — already includes `requests`; no new dependency required unless we add tests/tools later.
- `changelog.md` — document implementation after approval.

## API Contract (implementation target)
- **Method:** `POST`
- **URL:** `https://sdk.photoroom.com/v1/segment`
- **Headers:** `x-api-key: <PHOTOROOM_API_KEY>`
- **Body:** `multipart/form-data` with required field `image_file` (binary).
- **Success:** `200` with image body (`image/png` by default per docs) or JSON with `base64img` in some modes — Phase 3 should default to **binary PNG** response handling; if JSON is returned, decode `base64img` in a single code path.
- **Errors:** map JSON error bodies (`detail`, `status_code`, `type`) when present to user-safe messages.

## Error Handling Strategy
- Missing/placeholder API key at startup: optional warning; per-request check with clear reply.
- `401`/`403`: invalid or unauthorized key.
- `402`: billing/plan/quota messaging (user-friendly).
- `400`: invalid image or parameters.
- `429`: rate limit — ask user to retry later.
- Timeouts / connection errors: transient failure message.

## Non-Goals (Phase 3)
- Anthropic text generation (Phase 4).
- OpenClaw orchestration of Photoroom (later; Phase 5 / pipeline).
- Batch processing, webhooks, or async job queues.
- Photoroom **Image Editing API** (`image-api.photoroom.com` GET flow) unless we explicitly extend specs later.
