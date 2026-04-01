"""Centralised logging configuration for ToneDef.

Call :func:`configure_logging` once at application startup (``app.py``,
diagnostic scripts) to set up dual-handler logging:

    * **stderr** — WARNING and above for immediate visibility
    * **logs/tonedef.log** — INFO and above with rotation (5 MB x 3 backups)

Build scripts intentionally use ``print()`` for CLI progress output and
do not call this module.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from tonedef.paths import project_root
from tonedef.settings import settings

_LOGS_DIR = project_root() / "logs"
_LOG_FILE = _LOGS_DIR / "tonedef.log"
_FORMAT = "%(asctime)s %(name)s %(levelname)-8s %(message)s"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3

_configured = False


def configure_logging() -> None:
    """Set up root logger with stderr + rotating file handlers.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _configured
    if _configured:
        return
    _configured = True

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(_FORMAT)

    # stderr handler — WARNING+ only to avoid noise in Streamlit / terminals
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)

    # Rotating file handler — full detail at the configured level
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
