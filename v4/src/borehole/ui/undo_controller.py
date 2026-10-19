"""Stable per-borehole undo-manager registry."""

from __future__ import annotations

from ..application.undo_manager import UndoManager
from ..domain.models import Borehole


class UndoController:
    def __init__(self) -> None:
        self.managers: dict[str, UndoManager] = {}

    def clear(self) -> None:
        self.managers.clear()

    def get(self, borehole: Borehole | None) -> UndoManager | None:
        if borehole is None:
            return None
        return self.managers.setdefault(borehole.prefix, UndoManager())

    def remove(self, prefix: str) -> None:
        self.managers.pop(prefix, None)

    def migrate(self, old_prefix: str, new_prefix: str) -> None:
        if old_prefix == new_prefix:
            return
        manager = self.managers.pop(old_prefix, None)
        if manager is not None:
            self.managers[new_prefix] = manager
