# Plan - OpenClaw Initialization and Agent Setup (Phase 2)

## Technical Approach
1. Introduce a dedicated OpenClaw bootstrap module.
2. Add a base agent configuration for orchestration responsibilities.
3. Integrate OpenClaw startup in bot initialization flow.
4. Route selected Telegram interactions through an OpenClaw invocation helper.
5. Add guarded error handling and deterministic fallback messages.

## Planned File Structure
- `bot.py`: wire OpenClaw bootstrap and safe invocation path
- `services/openclaw_runtime.py`: initialize and expose runtime/agent handles
- `services/openclaw_agent.py`: define base agent instructions and invocation wrapper
- `specs/openclaw_init/*`: source-of-truth specs for this phase

## Interface Strategy
- Runtime initializer:
  - `init_openclaw() -> RuntimeHandle`
- Agent invocation helper:
  - `run_openclaw_agent(user_text: str, context: dict) -> str`
- Bot integration:
  - Telegram handlers call the helper and return formatted text output

## Error Handling Strategy
- Missing/invalid configuration -> startup warning + safe fallback responses
- Runtime initialization error -> do not crash process unexpectedly
- Agent invocation error -> return user-friendly message and log details

## Non-Goals for Phase 2
- No Photoroom API calls yet
- No Anthropic prompt generation pipeline yet
- No full multi-step catalog automation yet
