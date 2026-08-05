"""撤销/重做管理器。"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.enums import HoleType
from ..domain.models import BasicLayer, Borehole, TestRecord


def copy_layers(layers: list[BasicLayer]) -> list[BasicLayer]:
    return [
        BasicLayer(
            bottom_depth=layer.bottom_depth,
            lithology_code=layer.lithology_code,
            formation=layer.formation,
            structure=layer.structure,
            weathering=layer.weathering,
            description=layer.description,
        )
        for layer in layers
    ]


def copy_tests(tests: dict[str, list[TestRecord]]) -> dict[str, list[TestRecord]]:
    return {
        suffix: [TestRecord(values=list(record.values)) for record in records]
        for suffix, records in tests.items()
    }


@dataclass
class BoreholeSnapshot:
    prefix: str
    hole_type: HoleType
    main_lines: list[str]
    layers: list[BasicLayer]
    tests: dict[str, list[TestRecord]]
    dirty: bool
    dirty_suffixes: set[str]
    is_new: bool
    old_prefix: str | None

    @classmethod
    def capture(cls, borehole: Borehole) -> BoreholeSnapshot:
        return cls(
            prefix=borehole.prefix,
            hole_type=borehole.hole_type,
            main_lines=list(borehole.main.normalized_lines()),
            layers=copy_layers(borehole.layers),
            tests=copy_tests(borehole.tests),
            dirty=borehole.dirty,
            dirty_suffixes=set(borehole.dirty_suffixes),
            is_new=borehole.is_new,
            old_prefix=borehole.old_prefix,
        )

    def same_content(self, other: BoreholeSnapshot) -> bool:
        return (
            self.prefix == other.prefix
            and self.hole_type == other.hole_type
            and self.main_lines == other.main_lines
            and self.layers == other.layers
            and self.tests == other.tests
        )

    def restore(self, borehole: Borehole) -> None:
        borehole.prefix = self.prefix
        borehole.hole_type = self.hole_type
        borehole.main.lines = list(self.main_lines)
        borehole.layers = copy_layers(self.layers)
        borehole.tests = copy_tests(self.tests)
        borehole.dirty = self.dirty
        borehole.dirty_suffixes = set(self.dirty_suffixes)
        borehole.is_new = self.is_new
        borehole.old_prefix = self.old_prefix


@dataclass
class UndoAction:
    borehole: Borehole
    label: str
    before: BoreholeSnapshot
    after: BoreholeSnapshot


@dataclass
class CompositeUndoAction:
    """跨钻孔复合撤销操作（用于岩性描述同步等场景）。"""

    actions: list[UndoAction]
    label: str


Undoable = UndoAction | CompositeUndoAction


class UndoManager:
    def __init__(self, max_depth: int = 100) -> None:
        self.max_depth = max_depth
        self.undo_stack: list[Undoable] = []
        self.redo_stack: list[Undoable] = []

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def push(self, action: UndoAction) -> None:
        self.undo_stack.append(action)
        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def push_composite(self, action: CompositeUndoAction) -> None:
        self.undo_stack.append(action)
        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def pop_undo(self) -> Undoable | None:
        if not self.undo_stack:
            return None
        return self.undo_stack.pop()

    def pop_redo(self) -> Undoable | None:
        if not self.redo_stack:
            return None
        return self.redo_stack.pop()

    def push_redo(self, action: Undoable) -> None:
        self.redo_stack.append(action)

    def push_undo_without_clearing_redo(self, action: Undoable) -> None:
        self.undo_stack.append(action)
        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)
