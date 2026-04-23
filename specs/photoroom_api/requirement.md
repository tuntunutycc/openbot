# Requirement - Photoroom API Background Removal (Phase 3)

## Objective
Integrate Photoroom **Remove Background** into the Telegram bot so a user can send a product photo and receive a processed image (transparent or solid background per API options), without implementing Anthropic or OpenClaw orchestration in this phase.

## Business Logic
1. User sends an image to the bot (compressed photo and/or image document, per Telegram).
2. Bot downloads the file from Telegram, validates type/size within sensible limits.
3. Bot calls Photoroom **Remove Background** with `PHOTOROOM_API_KEY` (never embedded in code).
4. On success, bot sends the resulting image bytes back to the user in the same chat.
5. On failure, bot replies with a short, actionable error (auth, quota, bad image, network) and does not crash the process.

## Inputs
- Telegram message containing an image (`photo` and/or `document` with image mime type).
- Environment: `PHOTOROOM_API_KEY` (and optional future `PHOTOROOM_API_BASE` if we need to override the default host).
- Optional API parameters (Phase 3 baseline): `format` (png/jpg/webp), `channels` (rgba/alpha), `size` (preview/medium/hd/full) — exact defaults to be chosen in implementation.

## Outputs
- **Success:** processed image delivered to the user (binary photo in Telegram).
- **Failure:** user-visible error string; optional structured logging for operators (no secrets in logs).

## Constraints
- No hardcoded API keys; use `os.getenv()` only.
- Use official Photoroom HTTP contract: `POST` to `https://sdk.photoroom.com/v1/segment` with header `x-api-key` and multipart field `image_file` (per Photoroom quickstart).
- Reasonable timeouts and size limits; handle `400`, `402`, `403`, `429`, and `5xx` distinctly where possible.
- Preserve existing behavior: `/start`, text echo, `/agent` stub, and `agent:` routing from Phase 2.
- No Anthropic calls; no “full pipeline” via OpenClaw in Phase 3.

## References (external)
- Photoroom Remove Background quickstart: https://docs.photoroom.com/remove-background-api
