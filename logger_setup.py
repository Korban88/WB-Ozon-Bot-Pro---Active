"""
Dialog logging module.

Every user interaction is logged as a JSON line to logs/YYYY-MM-DD.log.
This makes it easy to:
  - Trace any user session step by step
  - Find errors with full context
  - Analyze which steps cause most drop-offs
  - Replay conversations for debugging

Log line format (one JSON object per line):
{
  "time": "2026-03-09T14:23:01.123",
  "user_id": 123456789,
  "username": "johndoe",
  "event": "step_completed",
  "step": "enter_title",
  "data": {"value": "Беспроводные наушники"},
  "error": null
}
"""

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from typing import Any

import config


# ── Internal Python logger (console output, startup errors, etc.) ─────────────
def _setup_python_logger() -> logging.Logger:
    logger = logging.getLogger("bot")
    logger.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(handler)

    return logger


# ── Daily dialog log file ──────────────────────────────────────────────────────
def _setup_dialog_file_handler() -> logging.Logger:
    os.makedirs(config.LOGS_DIR, exist_ok=True)

    dialog_logger = logging.getLogger("dialog")
    dialog_logger.setLevel(logging.DEBUG)
    dialog_logger.propagate = False  # don't send to root logger

    if not dialog_logger.handlers:
        log_path = os.path.join(config.LOGS_DIR, "dialog.log")
        # Rotate daily, keep 30 days of history
        file_handler = TimedRotatingFileHandler(
            log_path,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        dialog_logger.addHandler(file_handler)

    return dialog_logger


# ── Module-level logger instances ─────────────────────────────────────────────
log = _setup_python_logger()       # use for: log.info(), log.error(), etc.
_dialog = _setup_dialog_file_handler()


# ── Public API ─────────────────────────────────────────────────────────────────
def _write(
    user_id: int,
    username: str | None,
    event: str,
    step: str = "",
    data: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Write one JSON line to the daily dialog log."""
    record = {
        "time":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
        "user_id":  user_id,
        "username": username or "unknown",
        "event":    event,
        "step":     step,
        "data":     data or {},
        "error":    error,
    }
    _dialog.info(json.dumps(record, ensure_ascii=False))


def log_step(user_id: int, username: str | None, step: str, data: dict[str, Any] | None = None) -> None:
    """Log a completed dialog step with the user's answer."""
    _write(user_id, username, event="step_completed", step=step, data=data)


def log_event(user_id: int, username: str | None, event: str, data: dict[str, Any] | None = None) -> None:
    """Log a general event (bot started, restart, button clicked, etc.)."""
    _write(user_id, username, event=event, data=data)


def log_ai_call(user_id: int, username: str | None, service: str, success: bool,
                duration_ms: int, error: str | None = None) -> None:
    """Log an AI API call result."""
    _write(
        user_id, username,
        event="ai_call",
        step=service,
        data={"success": success, "duration_ms": duration_ms},
        error=error,
    )


def log_error(user_id: int, username: str | None, step: str, error: str) -> None:
    """Log an error with context."""
    _write(user_id, username, event="error", step=step, error=error)
    log.error("user=%s step=%s error=%s", user_id, step, error)
