# Plan - Custom Burmese Prompts & Smart Variations (Phase 8)

## Implementation Targets
Primary implementation surface:
- `services/anthropic_pipeline.py`

Secondary integration touchpoints (for schema consumption, not core translation logic):
- `services/catalog_pipeline.py`
- `services/pipeline_orchestrator.py` (if single-flow prompt output contract changes)

## 1) Single-Flow Prompt Overhaul

### System Prompt Redesign
Create a dedicated system prompt template for single-image prompt generation with explicit directives:
- role: "Master Prompt Engineer for commercial product imaging"
- language handling:
  - detect Burmese intent precisely
  - convert to natural, high-quality English
- enrichment policy:
  - include professional imaging terms when relevant
  - ensure photorealistic product-scene composition guidance
- output schema:
  - strict JSON only
  - key: `photoroom_background_prompt`
  - optional short rationale key only if explicitly needed by pipeline (default: omit)

### Quality Rules
- Must preserve user intent.
- Must avoid over-stylization if user asks for minimal realism.
- Must avoid irrelevant objects or scene drift.

## 2) Batch Variation Prompt Overhaul (`/catalog`)

### Structured Output Contract
Require strict JSON array length 3:
```json
[
  {"style_name":"minimal","background_prompt":"..."},
  {"style_name":"lifestyle","background_prompt":"..."},
  {"style_name":"premium","background_prompt":"..."}
]
```

### Distinctness Enforcement
Embed explicit constraints in system prompt:
- each variant must differ in:
  - environment/context
  - visual mood and lighting language
  - composition intent for catalog use
- but all must share the same product core intent from Burmese source input.

### Validation Layer
After model response:
- verify schema (array length, keys, styles)
- verify style uniqueness and prompt non-similarity (lightweight lexical checks + style-name checks)
- if invalid:
  - retry once with strict correction prompt
  - fallback to deterministic defaults (minimal/lifestyle/premium templates)

## 3) Fallback & Reliability
- Keep existing quota/billing fallback behavior unchanged for image generation.
- If Anthropic output fails quality/schema checks repeatedly:
  - use deterministic safe defaults rather than failing the user request.

## 4) Backward Compatibility
- No routing regression:
  - Phase 3 plain cutout path intact
  - Phase 4/5 ad path intact
  - Phase 6/7 catalog path intact
- Only prompt intelligence layer changes behavior quality.

## 5) Acceptance Criteria (for implementation)
- Burmese single prompts consistently produce high-quality English `background_prompt`.
- `/catalog` returns 3 clearly distinct, professional prompts aligned to core intent.
- Existing fallback behavior remains stable under credit/quota stress.
