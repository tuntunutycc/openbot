# Validation — AI Automation Pipeline (Phase 4 & 5)

## Success criteria
- **Caption + photo:** User receives a **final composite image** and **marketing copy** that reflect the caption intent (e.g. beach ad).
- **Photo only (no caption):** Existing **Phase 3** behavior still runs — background removal only, no Anthropic call, no `v2/edit`.
- **Caption only / no image:** No pipeline run; helpful hint only.
- **Failures:** Invalid keys, quota, or network errors produce **user-safe** messages; bot keeps running.
- **Secrets:** No API keys in logs, Telegram messages, or git.

## Test matrix

### 1. Phase 3 regression — photo without caption
- Send photo with **empty** caption (or no caption field depending on client).
- Expect: cut-out / remove-background result as today (no marketing text required).

### 2. Pipeline happy path — photo with caption
- Send photo with caption: *“Make this an ad with a beach background.”*
- Expect:
  - Final image shows subject on a beach-style (or prompt-consistent) generated background.
  - Marketing text is coherent and references product/ad intent.
  - Reasonable latency (document observed range in implementation notes).

### 3. Anthropic structured output
- Mock or integration test: caption in → JSON with both keys → parser accepts.
- Malformed model output: one retry or graceful error (no crash).

### 4. Photoroom segment
- Confirm cut-out has transparency suitable for `v2/edit` input (visual check: subject isolated).

### 5. Photoroom `v2/edit` with `background.prompt`
- Confirm request uses **cut-out** as `imageFile` and `referenceBox=originalImage`.
- Confirm error when API key lacks Plus/Image Editing entitlements (expect clear user message).

### 6. Error handling
- Wrong `ANTHROPIC_API_KEY`: user informed, no partial Photoroom spend after failure point where possible.
- Wrong `PHOTOROOM_API_KEY` on segment or edit: distinct, actionable messages.
- Timeouts: user informed; bot process alive.

### 7. OpenClaw /agent stub (regression)
- `/agent hello` still returns stub OpenClaw routing message until real orchestration is implemented.

## Completion checklist
- [ ] All test cases above pass on a real Telegram chat (or agreed staging equivalent).
- [ ] `changelog.md` updated for Phase 4 and Phase 5 implementation milestones.
- [ ] `requirements.txt` updated for any new dependencies.
- [ ] Specs (`specs/ai_pipeline/*`) reviewed and approved before merge to `main`.
