# Validation - OpenClaw Initialization and Agent Setup (Phase 2)

## Success Criteria
- OpenClaw runtime initializes successfully during bot startup.
- Base agent is available for invocation through a stable interface.
- Bot can call OpenClaw and return a valid response path.
- Existing `/start` and text echo behavior still works (no regression).
- Failures in OpenClaw path produce controlled, user-friendly responses.

## Test Steps
1. Startup validation
   - Run bot with required environment variables.
   - Confirm OpenClaw initialization completes without fatal errors.

2. Agent invocation validation
   - Trigger a message path routed through OpenClaw.
   - Confirm returned response payload is delivered to Telegram user.

3. Fault handling validation
   - Simulate OpenClaw initialization failure or invocation exception.
   - Confirm bot remains alive and sends graceful fallback response.

4. Regression validation
   - Call `/start` and verify expected startup text.
   - Send plain text and verify existing echo behavior remains intact.

## Completion Checklist
- [ ] Initialization and invocation paths verified locally
- [ ] Error scenarios handled without bot crash
- [ ] No regressions in existing bot commands/handlers
- [ ] Changelog updated with Phase 2 spec and implementation milestones
