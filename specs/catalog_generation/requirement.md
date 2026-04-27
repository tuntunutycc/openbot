# Requirement - Catalog Generation (Phase 6)

## Objective
Build a Telegram-driven catalog generation flow that transforms a user-provided product photo into a professional catalog-style visual output, optionally paired with concise marketing copy.

## User Story
- User sends a product photo (and optionally a caption with style instructions) to the Telegram bot.
- Bot returns a polished catalog layout image suitable for e-commerce listings, social posts, and ad creatives.

## Business Logic
1. Receive Telegram image input (photo or supported image document), with optional text instruction.
2. Validate image size/type and normalize the input into a consistent internal format.
3. Produce an isolated product subject (reuse/remove-background pipeline when needed).
4. Build a catalog composition plan (layout style, spacing, focal placement, decorative elements, optional text slots).
5. Render a catalog output using Photoroom image-editing/template-like capabilities and deterministic style presets.
6. Optionally generate or refine short marketing text (headline/body/CTA) using existing Anthropic flow.
7. Return final catalog image and optional copy to the same Telegram conversation.

## Inputs
- Required: Telegram image (`photo` or supported `document`)
- Optional: caption/instruction text (style preferences, campaign tone)
- Environment variables:
  - `TELEGRAM_BOT_TOKEN`
  - `PHOTOROOM_API_KEY`
  - `ANTHROPIC_API_KEY` (if text generation is enabled for this flow)

## Outputs
- Primary: one catalog-style rendered image
- Secondary (optional): generated marketing text delivered in caption or follow-up message

## Constraints
- Never hardcode API keys; use `os.getenv()` and `.env`.
- Preserve existing Phase 3 and Phase 4/5 behavior without regression.
- Handle quota/billing/network issues gracefully using fallback strategies.
- Keep output style consistent via predefined templates/presets to reduce variance.

## Out of Scope (Phase 6 MVP)
- Multi-page PDF catalog exports
- Inventory/database integrations
- Persistent brand profile management across users
