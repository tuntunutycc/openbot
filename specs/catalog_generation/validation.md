# Validation - Catalog Generation (Phase 6)

## Success Criteria
- Bot can generate a professional catalog-style image from a user-provided product photo.
- Style presets produce visibly distinct but stable outputs (minimal/premium/lifestyle or equivalent).
- Existing Phase 3 and Phase 4/5 flows continue to work without regressions.
- Fallback behavior preserves end-to-end usability when APIs are quota-limited.

## Test Plan

1. **Catalog happy path**
   - Input: product photo + catalog instruction.
   - Expect: final catalog image returned with correct composition and quality.

2. **Style preset validation**
   - Run same product photo across at least 2 style modes.
   - Expect: different yet consistent layout outputs; subject remains clear and centered appropriately.

3. **Text output validation (optional copy)**
   - If copy is enabled, verify caption/follow-up messaging rules and Telegram length handling.

4. **Photoroom quota/billing fallback**
   - Simulate or force quota path.
   - Expect: no crash; fallback image returned and user receives clear message/copy.

5. **Anthropic fallback compatibility**
   - Simulate low-credit or API failure path.
   - Expect: mock/fallback copy behavior remains functional without blocking image delivery.

6. **Regression checks**
   - Photo without caption still supports Phase 3 behavior.
   - Phase 4/5 caption-driven ad pipeline still works.
   - `/start`, `/agent`, and text echo still function.

## Completion Checklist
- [ ] Catalog generation flow works in real Telegram chat
- [ ] All fallback paths verified (Photoroom + Anthropic)
- [ ] No regressions in existing phases
- [ ] `changelog.md` updated for Phase 6 spec creation and future implementation milestones
