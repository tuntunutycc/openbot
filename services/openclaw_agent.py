from typing import Any

from services.openclaw_runtime import RuntimeHandle


BASE_AGENT_INSTRUCTIONS = (
    "You are the OpenBot orchestration agent. "
    "Coordinate user intents into reliable automation steps."
)


def run_openclaw_agent(user_text: str, context: dict[str, Any], handle: RuntimeHandle) -> str:
    """
    Run a single OpenClaw agent invocation.

    Returns a deterministic fallback message if runtime is unavailable
    or invocation fails, so Telegram handlers remain stable.
    """
    if not handle.is_ready:
        return "OpenClaw is not available yet. Please try again shortly."

    try:
        # Placeholder invocation contract for Phase 2.
        # A concrete SDK call will be wired in later phases.
        chat_id = context.get("chat_id", "unknown")
        return (
            f"[OpenClaw:{handle.agent.get('name')}] "
            f"chat={chat_id} request='{user_text}'"
        )
    except Exception:
        return "I could not process your request with OpenClaw right now."
