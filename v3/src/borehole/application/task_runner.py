"""Single-flight Qt background task lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal


class _TaskThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[], Any], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._operation = operation

    def run(self) -> None:
        try:
            self.succeeded.emit(self._operation())
        except Exception as error:
            self.failed.emit(str(error))


class TaskRunner(QObject):
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.worker: _TaskThread | None = None
        self._on_success: Callable[[Any], None] | None = None
        self._on_error: Callable[[str], None] | None = None

    @property
    def running(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def start(
        self,
        operation: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[str], None],
    ) -> bool:
        if self.worker is not None:
            return False
        self._on_success = on_success
        self._on_error = on_error
        worker = _TaskThread(operation, self)
        self.worker = worker
        worker.succeeded.connect(self._handle_success)
        worker.failed.connect(self._handle_error)
        worker.finished.connect(self._handle_finished)
        worker.start()
        return True

    def wait(self, timeout_ms: int = 5000) -> bool:
        worker = self.worker
        return worker is None or worker.wait(timeout_ms)

    def _handle_success(self, result: Any) -> None:
        callback = self._on_success
        if callback is None:
            return
        try:
            callback(result)
        except Exception as error:
            self._handle_error(str(error))

    def _handle_error(self, error: str) -> None:
        callback = self._on_error
        if callback is not None:
            callback(error)

    def _handle_finished(self) -> None:
        worker = self.worker
        self.worker = None
        self._on_success = None
        self._on_error = None
        if worker is not None:
            worker.deleteLater()
        self.finished.emit()
