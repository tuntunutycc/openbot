# Requirement - Batch Variations (Phase 7)

## Objective
Upgrade `/catalog` so the bot returns multiple design candidates (target: 3 variations) for the same product image, enabling a human designer to choose and refine the best option.

## User Story
- User sends a product photo with `/catalog ...` instruction.
- Bot generates three distinct catalog design directions (for example: minimalist, premium, vibrant).
- Bot returns all three results together as a Telegram album (`MediaGroup`) plus optional supporting text.

## Business Logic
1. Ingest Telegram image + `/catalog` instruction.
2. Generate a product cutout baseline once (reuse existing Phase 6 cutout flow).
3. Ask Claude to produce a JSON array of exactly 3 distinct style prompts for Photoroom editing:
   - variation 1: minimalist-like
   - variation 2: premium-like
   - variation 3: vibrant/lifestyle-like
4. For each prompt, call Photoroom Image Editing API and generate one variation image.
5. Return all successful variation outputs as one Telegram `send_media_group` response.
6. If quota/billing blocks variation generation, avoid crashing and return fallback output safely.

## Inputs
- Telegram image (`photo` or supported image `document`)
- `/catalog` instruction text
- Environment: `PHOTOROOM_API_KEY`, `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`

## Outputs
- Preferred: 3 catalog variation images in one Telegram album
- Fallback: single cutout mockup if quotas prevent variation generation
- Optional: concise summary text describing variation intent

## Constraints
- No hardcoded secrets.
- Preserve Phase 3 (single cutout) and Phase 4/5 (ad pipeline) behavior.
- Keep style outputs intentionally distinct and deterministic enough for repeatable review.
- Do not fail entire request if one variation generation fails.
