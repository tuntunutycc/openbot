# Requirement - Custom Burmese Prompts & Smart Variations (Phase 8)

## Objective
Elevate prompt intelligence so Burmese user instructions produce high-quality, professional, and commercially useful English prompts for Photoroom in both:
- single-image generation flow, and
- `/catalog` batch-variation flow.

## Scope
This phase focuses on **prompt behavior and quality control** (not rendering engine changes):
1. Burmese-to-English prompt engineering for single-image requests.
2. Burmese-driven, intentionally distinct 3-variation prompt generation for catalog batch mode.
3. Strong instruction policy in Anthropic/OpenClaw prompt layer to enforce consistency and quality.

## Core Business Requirements

### A) Single Image Flow (Burmese Description)
- When user writes a detailed Burmese description, Claude must:
  1. understand the true visual intent in Burmese,
  2. translate and expand it into polished English prompt text,
  3. enrich with professional photo/art direction terms when appropriate:
     - cinematic lighting
     - depth of field
     - photorealistic
     - high-detail / 8k-quality style wording
  4. output one ultimate `background_prompt` tailored for Photoroom.
- Output should remain faithful to user intent (no random theme drift).

### B) Catalog Batch Flow (3 Images)
- For `/catalog` + Burmese instruction, Claude must generate exactly 3 distinct variants:
  1. **Minimalist** interpretation
  2. **Lifestyle/Contextual** interpretation
  3. **Premium/Luxury** interpretation
- Variants must not be near-duplicates; each should have distinct setting, mood, composition language, and commercial purpose.
- All variants must still align with the same core user intent and product context.

### C) Prompt Policy / Guardrails
- System prompt in `services/anthropic_pipeline.py` must be redesigned to explicitly enforce:
  - faithful Burmese intent extraction
  - English output quality standards
  - strict JSON output schema
  - variation distinctness constraints for batch mode
- If model output violates schema or distinctness constraints, retry/fallback policy must apply without crashing user flow.

## Inputs
- User image input (already handled by existing flows)
- User instruction in Burmese (single flow or `/catalog`)
- Existing API keys and pipeline context

## Outputs
- Single flow: one production-grade English `background_prompt`
- Batch flow: JSON array of exactly 3 professionally distinct prompt objects

## Constraints
- No hardcoded credentials.
- Preserve existing fallback safety for API quota/billing.
- Maintain backward compatibility with prior phases (Phase 3/4/5/6/7 routes).
