# Validation - Photoroom API Background Removal (Phase 3)

## Success Criteria
- User sends a normal product photo; bot returns a background-removed image within expected latency for `size=preview` or `medium` (exact default documented in implementation).
- Bot rejects or safely handles obviously non-image documents without crashing.
- With invalid `PHOTOROOM_API_KEY`, user gets a clear error, not a stack trace in Telegram.
- With network failure or timeout, bot stays up and returns a friendly message.
- Regression: `/start`, plain text echo, `/agent` and `agent:` stub behavior unchanged.

## Test Steps
1. **Environment**
   - `.env` contains valid `PHOTOROOM_API_KEY` and `TELEGRAM_BOT_TOKEN`.
   - Start bot from project root using `.venv`; confirm no import errors.

2. **Happy path — photo**
   - Send an image as a **photo** (not file-only if possible).
   - Expect a processed image reply; visually confirm background removal.

3. **Happy path — document**
   - Send the same image as a **file** / document (if handler supports it).
   - Expect same class of success or a clear “please send as photo” if out of scope.

4. **Invalid API key**
   - Temporarily set `PHOTOROOM_API_KEY` to an invalid value in `.env`, restart bot.
   - Send image; expect auth/forbidden style user message.

5. **Rate limit / quota (if observable)**
   - If testing triggers `429` or `402`, confirm message explains retry or billing.

6. **Regression**
   - `/start` shows expected text including OpenClaw status line.
   - Plain text echoes.
   - `/agent test` returns stub OpenClaw line, not Photoroom error.

## Completion Checklist
- [ ] All success criteria met on a real Telegram chat
- [ ] No unhandled exceptions in console during tests
- [ ] `changelog.md` updated after implementation merge (post-approval)
- [ ] No secrets committed; `.env` remains gitignored
