import logging
import sys
from pathlib import Path

from borehole.infrastructure.logging_setup import install_exception_hook, setup_logging


def _flush_borehole_handlers() -> None:
    for handler in logging.getLogger("borehole").handlers:
        handler.flush()


def test_setup_logging_writes_to_data_logs(tmp_path: Path) -> None:
    log_path = setup_logging(tmp_path)
    assert log_path is not None

    logging.getLogger("borehole.test").error("diagnostic message")
    _flush_borehole_handlers()

    assert log_path == tmp_path / ".Data" / "logs" / "borehole-v3.log"
    assert "diagnostic message" in log_path.read_text(encoding="utf-8")


def test_setup_logging_falls_back_when_primary_path_is_blocked(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("file", encoding="utf-8")
    fallback = tmp_path / "fallback"

    log_path = setup_logging(blocked, fallback)
    assert log_path is not None

    assert log_path == fallback / "borehole-v3.log"
    assert log_path.exists()


def test_exception_hook_records_traceback(tmp_path: Path) -> None:
    log_path = setup_logging(tmp_path)
    assert log_path is not None
    previous = sys.excepthook
    try:
        install_exception_hook()
        try:
            raise RuntimeError("uncaught detail")
        except RuntimeError:
            exception = sys.exc_info()
        sys.excepthook(*exception)
        _flush_borehole_handlers()
    finally:
        sys.excepthook = previous

    content = log_path.read_text(encoding="utf-8")
    assert "uncaught detail" in content
    assert "Traceback" in content
