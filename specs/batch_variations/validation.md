# Validation - Batch Variations (Phase 7)

## Success Criteria
- `/catalog` produces 3 distinct design variations from one input image.
- Bot delivers results as Telegram album (`MediaGroup`) when 2+ images are available.
- Quota/billing constraints do not crash the pipeline; fallback output is still delivered.
- Existing flows (Phase 3 and Phase 4/5) remain unaffected.

## Test Plan

1. **Happy Path Batch**
   - Input: `/catalog create professional options` + product image.
   - Expect: 3 unique outputs returned in one album.

2. **Variation Distinctness**
   - Confirm outputs differ in style characteristics (minimal/premium/vibrant or equivalent).

3. **Claude JSON Validation**
   - Simulate malformed Claude output.
   - Expect: fallback to deterministic default 3 prompts and still return album.

4. **Partial Photoroom Failure**
   - Simulate one variant hitting error/quota.
   - Expect: remaining successful images plus fallback replacement for failed slot.

5. **Full Quota Fallback**
   - Simulate all three variant calls returning 402/403.
   - Expect: single cutout fallback image returned with non-crashing response.

6. **Telegram MediaGroup Compatibility**
   - Validate binary-to-media conversion and album send API behavior.
   - Ensure caption strategy does not break album send.

7. **Regression**
   - Photo without caption: Phase 3 unchanged.
   - Caption non-catalog: Phase 4/5 ad pipeline unchanged.
   - `/agent` and text echo unaffected.

## Completion Checklist
- [ ] Batch variation generation works in Telegram with real image input
- [ ] Album delivery verified end-to-end
- [ ] Quota fallback path verified (partial and full failure)
- [ ] No regressions in earlier phases
- [ ] `changelog.md` updated with Phase 7 spec milestone
