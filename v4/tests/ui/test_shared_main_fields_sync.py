from pathlib import Path

from PySide6.QtWidgets import QMessageBox

import borehole.ui.main_window as main_window_module
from borehole.application.project_service import create_empty_project
from borehole.application.undo_manager import CompositeUndoAction
from borehole.domain.enums import HoleType
from borehole.domain.models import (
    MAIN_INDEX_DESIGN_UNIT,
    MAIN_INDEX_PROJECT,
    Borehole,
    MainFileData,
    ProjectData,
)
from borehole.ui.main_window import MainWindow


def _window(qtbot, monkeypatch) -> MainWindow:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "_project", create_empty_project()))
    return window


def _borehole(folder: Path, prefix: str, project: str, design_unit: str) -> Borehole:
    lines = [""] * 16
    lines[MAIN_INDEX_PROJECT] = project
    lines[MAIN_INDEX_DESIGN_UNIT] = design_unit
    lines[0] = prefix
    return Borehole(
        prefix=prefix,
        folder=folder,
        hole_type=HoleType.ZK,
        main=MainFileData(lines=lines),
    )


def _load_boreholes(window: MainWindow, source: Borehole, targets: list[Borehole]) -> None:
    window._project = ProjectData(
        folder=source.folder,
        boreholes={borehole.prefix: borehole for borehole in [source, *targets]},
    )
    window._refresh_borehole_list()
    window._load_current_borehole(source)
    window._select_in_tree(source.prefix)


def _edit_field(window: MainWindow, index: int, value: str) -> None:
    window._main_file_page._begin_field_edit(index)
    window._main_file_page._entries[index].setText(value)
    window._main_file_page._on_edit_finished(index)


def test_project_field_sync_is_optional_and_undoable(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch)
    source = _borehole(tmp_path, "ZK1", "旧项目", "设计单位")
    target = _borehole(tmp_path, "ZK2", "其他项目", "设计单位")
    _load_boreholes(window, source, [target])
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    _edit_field(window, MAIN_INDEX_PROJECT, "新项目")

    assert source.main.normalized_lines()[MAIN_INDEX_PROJECT] == "新项目"
    assert target.main.normalized_lines()[MAIN_INDEX_PROJECT] == "新项目"
    manager = window._get_undo_manager(source)
    assert manager is not None
    assert isinstance(manager.undo_stack[-1], CompositeUndoAction)

    window._undo()
    assert source.main.normalized_lines()[MAIN_INDEX_PROJECT] == "旧项目"
    assert target.main.normalized_lines()[MAIN_INDEX_PROJECT] == "其他项目"
    window._redo()
    assert source.main.normalized_lines()[MAIN_INDEX_PROJECT] == "新项目"
    assert target.main.normalized_lines()[MAIN_INDEX_PROJECT] == "新项目"


def test_design_unit_field_can_skip_sync(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch)
    source = _borehole(tmp_path, "ZK1", "项目", "旧单位")
    target = _borehole(tmp_path, "ZK2", "项目", "其他单位")
    _load_boreholes(window, source, [target])
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )

    _edit_field(window, MAIN_INDEX_DESIGN_UNIT, "新单位")

    assert source.main.normalized_lines()[MAIN_INDEX_DESIGN_UNIT] == "新单位"
    assert target.main.normalized_lines()[MAIN_INDEX_DESIGN_UNIT] == "其他单位"
