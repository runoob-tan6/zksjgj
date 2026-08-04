"""Application logging with a writable fallback location."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from types import TracebackType

from .settings import get_app_base_dir

LOG_NAME = "borehole-v3.log"
_HANDLER_MARKER = "_borehole_v3_handler"


def _fallback_log_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".borehole-v3"
    return base / "BoreholeEditorV3" / "logs"


def _create_handler(log_dir: Path) -> TimedRotatingFileHandler:
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(
        log_dir / LOG_NAME,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    setattr(handler, _HANDLER_MARKER, True)
    return handler


def setup_logging(app_base_dir: Path | None = None, fallback_dir: Path | None = None) -> Path | None:
    logger = logging.getLogger("borehole")
    for existing_handler in list(logger.handlers):
        if getattr(existing_handler, _HANDLER_MARKER, False):
            logger.removeHandler(existing_handler)
            existing_handler.close()

    primary = (app_base_dir or get_app_base_dir()) / ".Data" / "logs"
    fallback = fallback_dir or _fallback_log_dir()
    file_handler: TimedRotatingFileHandler | None = None
    for directory in (primary, fallback):
        try:
            file_handler = _create_handler(directory)
            break
        except OSError:
            continue
    if file_handler is None:
        return None

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.propagate = False
    return Path(file_handler.baseFilename)


def install_exception_hook() -> None:
    def log_uncaught(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        logging.getLogger("borehole.uncaught").critical(
            "Uncaught application exception",
            exc_info=(exception_type, exception, traceback),
        )

    sys.excepthook = log_uncaught
