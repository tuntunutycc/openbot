# Changelog

## 2026-04-22
- Project initialized with Spec-Driven Development (SDD) structure, Cursor rules, and roadmap.
- Phase 1 initialized: added `.gitignore`, created `.env` placeholders, and implemented a minimal Telegram bot (`bot.py`) with `/start` and text echo handlers using `pyTelegramBotAPI` and `python-dotenv`.
- Added `requirements.txt` with core dependencies (`pyTelegramBotAPI`, `python-dotenv`, `requests`) and installed them into the local `.venv`.
- Confirmed manually generated `requirements.txt` (via `pip freeze`) is included on `feature/phase2-openclaw-init` to support dependency tracking for Ubuntu server deployment.
- Added `TELEGRAM_BOT_USERNAME=@photoadsclawbot` to `.env` for explicit bot identity configuration.
- Upgraded SDD workflow with a Feature-Based SDD rule in `.cursorrules`, created branch `feature/phase3-photoroom`, and added Phase 3 Photoroom specs: `specs/photoroom_api/requirement.md`, `specs/photoroom_api/plan.md`, and `specs/photoroom_api/validation.md` for approval before coding.
- Created Phase 2 OpenClaw spec package on branch `feature/phase2-openclaw-specs`: `specs/openclaw_init/requirement.md`, `specs/openclaw_init/plan.md`, and `specs/openclaw_init/validation.md` for approval before implementation.
- Implemented Phase 2 OpenClaw runtime scaffolding: added `services/openclaw_runtime.py` and `services/openclaw_agent.py`, wired `bot.py` with startup initialization, `/agent` command routing, `agent:` text routing, and deterministic fallback behavior when OpenClaw is unavailable.
- Installed `openclaw` in the local `.venv` and added it to `requirements.txt` for Phase 2 dependency completeness.

## 2026-04-23
- Updated `ANTHROPIC_API_KEY` in `.env` (replaced placeholder; value not logged here).
- Updated `PHOTOROOM_API_KEY` in `.env` (replaced placeholder; value not logged here).
- Fixed OpenClaw import path: alias `cmdop.exceptions.TimeoutError` to `ConnectionTimeoutError` before loading `openclaw`, and added explicit `tenacity` dependency for CMDOP generated clients.
- Merged `feature/phase2-openclaw-specs` into `main` (Phase 2 approved) and deleted the feature branch locally.
