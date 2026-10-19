"""撤销管理器单元测试。"""

from __future__ import annotations

from pathlib import Path

from borehole.application.undo_manager import (
    BoreholeSnapshot,
    UndoAction,
    UndoManager,
)
from borehole.domain.enums import HoleType
from borehole.domain.models import Borehole, MainFileData


def _make_borehole(prefix="ZK1") -> Borehole:
    return Borehole(
        prefix=prefix,
        folder=Path("/tmp"),
        hole_type=HoleType.ZK,
        main=MainFileData(lines=[prefix, "10"] + [""] * 14),
    )


class TestUndoManager:
    def test_empty_undo(self):
        mgr = UndoManager()
        assert not mgr.can_undo()
        assert mgr.pop_undo() is None

    def test_push_and_undo(self):
        mgr = UndoManager()
        b = _make_borehole()
        before = BoreholeSnapshot.capture(b)
        b.main.lines[1] = "20"
        after = BoreholeSnapshot.capture(b)
        mgr.push(UndoAction(borehole=b, label="修改孔深", before=before, after=after))
        assert mgr.can_undo()
        action = mgr.pop_undo()
        assert action.label == "修改孔深"

    def test_redo_after_undo(self):
        mgr = UndoManager()
        b = _make_borehole()
        before = BoreholeSnapshot.capture(b)
        b.main.lines[1] = "20"
        after = BoreholeSnapshot.capture(b)
        mgr.push(UndoAction(borehole=b, label="test", before=before, after=after))
        action = mgr.pop_undo()
        mgr.push_redo(action)
        assert mgr.can_redo()

    def test_max_depth(self):
        mgr = UndoManager(max_depth=3)
        b = _make_borehole()
        for i in range(5):
            before = BoreholeSnapshot.capture(b)
            b.main.lines[1] = str(i + 20)
            after = BoreholeSnapshot.capture(b)
            mgr.push(UndoAction(borehole=b, label=f"edit {i}", before=before, after=after))
        assert len(mgr.undo_stack) == 3


class TestBoreholeSnapshot:
    def test_capture_and_restore(self):
        b = _make_borehole()
        snap = BoreholeSnapshot.capture(b)
        b.main.lines[1] = "99"
        b.prefix = "ZK2"
        snap.restore(b)
        assert b.prefix == "ZK1"
        assert b.main.lines[1] == "10"

    def test_same_content(self):
        b = _make_borehole()
        s1 = BoreholeSnapshot.capture(b)
        s2 = BoreholeSnapshot.capture(b)
        assert s1.same_content(s2)

    def test_different_content(self):
        b = _make_borehole()
        s1 = BoreholeSnapshot.capture(b)
        b.main.lines[1] = "20"
        s2 = BoreholeSnapshot.capture(b)
        assert not s1.same_content(s2)
