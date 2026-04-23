import os
from dataclasses import dataclass
from typing import Any


@dataclass
class RuntimeHandle:
    is_ready: bool
    runtime: Any = None
    agent: Any = None
    reason: str = ""


def init_openclaw() -> RuntimeHandle:
    """
    Initialize OpenClaw runtime and base agent handle.

    This function is intentionally defensive so the bot keeps running
    even when OpenClaw is not installed or is misconfigured.
    """
    try:
        # openclaw expects cmdop.exceptions.TimeoutError; newer cmdop uses
        # ConnectionTimeoutError only. Patch before importing openclaw.
        import cmdop.exceptions as _cmdop_exc  # type: ignore

        if not hasattr(_cmdop_exc, "TimeoutError"):
            _cmdop_exc.TimeoutError = _cmdop_exc.ConnectionTimeoutError  # type: ignore[attr-defined]

        import openclaw  # type: ignore
    except Exception as exc:
        return RuntimeHandle(
            is_ready=False,
            reason=f"OpenClaw import failed: {exc}",
        )

    agent_name = os.getenv("OPENCLAW_AGENT_NAME", "openbot-orchestrator")
    base_agent = {
        "name": agent_name,
        "role": "Orchestrate automation tasks for Telegram user requests.",
    }

    return RuntimeHandle(
        is_ready=True,
        runtime=openclaw,
        agent=base_agent,
        reason="OpenClaw initialized successfully.",
    )
