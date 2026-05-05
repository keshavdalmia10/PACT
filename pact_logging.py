"""Central logging config — file + console handlers, idempotent.

Usage in any module:

    from pact_logging import get_logger
    log = get_logger(__name__)
    log.info("...")

Rotating file at logs/pact.log (DEBUG); console at INFO. All PACT loggers
live under the "pact" namespace so 3rd-party noise (openai, urllib3, etc)
stays at WARNING by default.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "pact.log"

_CONFIGURED = False


def setup_logging(
    console_level: int | None = None,
    file_level: int = logging.DEBUG,
) -> None:
    """Configure handlers under the 'pact' namespace. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    if console_level is None:
        env = os.environ.get("PACT_LOG_LEVEL", "INFO").upper()
        console_level = getattr(logging, env, logging.INFO)

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    pact_logger = logging.getLogger("pact")
    pact_logger.setLevel(min(console_level, file_level))
    pact_logger.propagate = False

    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = RotatingFileHandler(LOG_FILE, maxBytes=10_000_000, backupCount=5, encoding="utf-8")
    fh.setLevel(file_level)
    fh.setFormatter(file_fmt)
    pact_logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    pact_logger.addHandler(ch)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a child of the 'pact' logger. Auto-prefixes if missing."""
    setup_logging()
    if not name.startswith("pact"):
        name = f"pact.{name}"
    return logging.getLogger(name)
