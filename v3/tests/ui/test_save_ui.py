from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

import borehole.ui.main_window as main_window_module
from borehole.application.project_service import create_empty_project, load_project
from borehole.application.save_service import SaveService
from borehole.domain.enums import HoleType
from borehole.domain.models import BasicLayer, Borehole, MainFileData, ProfileFile
from borehole.domain.models import TestRecord as Record
from borehole.ui.main_window import MainWindow
from borehole.ui.test_data_page import TestDataPage as DataPage


def test_sync_save_delegates_to_save_service(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    calls: list[str] = []

    class FakeSaveService:
        def __init__(self, _project) -> None:
            pass

        def summary(self):
            return SimpleNamespace(has_changes=True)

        def save(self):
            calls.append("save")
            return SimpleNamespace(as_tuple=lambda: ([], 0))

    monkeypatch.setattr(main_window_module, "SaveService", FakeSaveService, raising=False)
    window = MainWindow()
    qtbot.addWidget(window)
    window._project = create_empty_project()

    assert window._save_data_sync()
    assert calls == ["save"]

    monkeypatch.setattr(main_window_module, "SaveService", SaveService)
    window.close()


@pytest.mark.parametrize("previous_key", ["profile:H1", "profile_extra:H1:k", "profile:H2"])
@pytest.mark.parametrize("return_via_tree", [False, True])
@pytest.mark.parametrize("expanded", [False, True])
def test_save_basic_data_after_profile_keeps_borehole_view(
    qtbot, monkeypatch, tmp_path, previous_key, return_via_tree, expanded,
) -> None:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "_project", create_empty_project()))
    window._project.folder = tmp_path
    hole = Borehole(
        prefix="ZK1", folder=tmp_path, hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "20"]), layers=[BasicLayer(bottom_depth="20")], is_new=True,
    )
    window._project.boreholes[hole.prefix] = hole
    window._project.profile_files = {
        name: ProfileFile(name=name, path=tmp_path / name, extra_files={"k": "ZK1,40,0,N"})
        for name in ("H1", "H2")
    }
    SaveService(window._project).save()
    window._load_current_borehole(hole)
    window._refresh_borehole_list()
    window._select_in_tree(previous_key)
    if return_via_tree:
        window._select_in_tree("ZK1")
    else:
        window._tabs.setCurrentWidget(window._main_file_page)

    profile_group = window._tree.topLevelItem(2)
    for index in range(profile_group.childCount()):
        profile_group.child(index).setExpanded(expanded)
    table = window._main_file_page._basic_data_page._table
    cell = table.model().index(0, 5)
    table.setCurrentIndex(cell)
    assert table.model().setData(cell, "2")
    observed = []

    def inspect_completion(*_args):
        group = window._tree.topLevelItem(2)
        observed.append((
            window._tree_controller.current_key(),
            window._tabs.currentWidget(),
            [group.child(index).isExpanded() for index in range(group.childCount())],
            table.currentIndex().row(),
            table.currentIndex().column(),
        ))

    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", inspect_completion)
    window._save_data()
    qtbot.waitUntil(lambda: not window._task_runner.running)

    expected_key = "ZK1" if return_via_tree else previous_key
    assert observed == [(expected_key, window._main_file_page, [expanded, expanded], 0, 5)]
    assert not hole.dirty
    assert load_project(tmp_path).boreholes["ZK1"].layers[0].weathering == "2"


@pytest.mark.parametrize("key", ["profile:H1", "profile_extra:H1:k", "project_file:0yzk:zkt", "extra:ZK1:x"])
def test_finish_save_keeps_selected_data_file_and_text_editor(qtbot, monkeypatch, tmp_path, key) -> None:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "_project", create_empty_project()))
    hole = Borehole(
        prefix="ZK1", folder=tmp_path, hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "20"]), extra_files={"x": "extra"},
    )
    window._project.boreholes[hole.prefix] = hole
    window._project.profile_files["H1"] = ProfileFile(
        name="H1", path=tmp_path / "H1", content="main", extra_files={"k": "profile-k"},
    )
    window._project.project_files["0yzk"] = ProfileFile(
        name="0yzk", path=tmp_path / "0yzk", extra_files={"zkt": "ZK1"},
    )
    window._load_current_borehole(hole)
    window._refresh_borehole_list()
    window._select_in_tree("profile_extra:H1:k")
    window._select_in_tree(key)
    editor = window._extra_text_page._text
    editor.selectAll()
    selected_text = editor.textCursor().selectedText()
    observed = []
    monkeypatch.setattr(
        QMessageBox, "information",
        lambda *_args: observed.append((window._tree_controller.current_key(), window._tabs.currentWidget())),
    )

    window._finish_save(([], 0))

    assert observed == [(key, window._extra_text_page)]
    assert editor.textCursor().selectedText() == selected_text
    editor.insertPlainText("updated")
    if key == "profile:H1":
        assert window._project.profile_files["H1"].content == "updated"
    elif key == "profile_extra:H1:k":
        assert window._project.profile_files["H1"].extra_files["k"] == "updated"
    elif key == "project_file:0yzk:zkt":
        assert window._project.project_files["0yzk"].extra_files["zkt"] == "updated"
    else:
        assert hole.extra_files["x"] == "updated"


def test_test_data_scroll_position_can_be_restored_after_reloading(qtbot) -> None:
    borehole = Borehole(
        prefix="ZK1",
        folder=Path("."),
        hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "20"]),
        tests={
            suffix: [Record([str(index), "", ""]) for index in range(12)]
            for suffix in ("o", "q", "m", "n", "e", "f", "l")
        },
    )
    page = DataPage()
    qtbot.addWidget(page)
    page.load_borehole(borehole)
    page.show()
    qtbot.wait(50)
    scrollbar = page._scroll.verticalScrollBar()
    assert scrollbar.maximum() > 0

    saved_position = scrollbar.maximum() // 2
    scrollbar.setValue(saved_position)
    page.load_borehole(borehole)
    qtbot.wait(50)
    page.restore_scroll_position(saved_position)
    qtbot.wait(50)

    assert scrollbar.value() == saved_position


@pytest.mark.parametrize("suffix", ["o", "q", "e", "f"])
@pytest.mark.parametrize("real_dialog", [False, True])
def test_finish_save_keeps_test_scroll_and_selected_cell(qtbot, monkeypatch, tmp_path, suffix, real_dialog) -> None:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "_project", create_empty_project()))
    borehole = Borehole(
        prefix="ZK1", folder=tmp_path, hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "20"]),
        tests={key: [Record([str(row), "", ""]) for row in range(12)] for key in ("o", "q", "e", "f")},
    )
    window._project.boreholes[borehole.prefix] = borehole
    window._load_current_borehole(borehole)
    window._refresh_borehole_list()
    page = window._test_data_page
    window._tabs.setCurrentWidget(page)
    window.show()
    window.activateWindow()
    table = page._sections[suffix]._table
    table.setCurrentIndex(table.model().index(9, 1))
    table.setFocus()
    qtbot.wait(50)
    position = page.scroll_position()
    table_position = table.verticalScrollBar().value()
    assert QApplication.focusWidget() is table

    scroll_movements = []
    page._scroll.verticalScrollBar().valueChanged.connect(scroll_movements.append)
    during_dialog = []

    def inspect_dialog(*_):
        qtbot.wait(50)
        current_table = page._sections[suffix]._table
        during_dialog.append((
            page.scroll_position(), current_table is table,
            current_table.currentIndex().row(), current_table.verticalScrollBar().value(),
        ))
        if real_dialog:
            QApplication.activeModalWidget().accept()

    if real_dialog:
        QTimer.singleShot(0, inspect_dialog)
    else:
        monkeypatch.setattr(QMessageBox, "information", inspect_dialog)
    window._finish_save(([], 0))
    qtbot.wait(50)

    assert during_dialog == [(position, True, 9, table_position)]
    assert all(value == position for value in scroll_movements)
    assert page.scroll_position() == position
    restored_table = page._sections[suffix]._table
    assert restored_table is table
    assert restored_table.currentIndex().row() == 9
    assert restored_table.currentIndex().column() == 1
    assert restored_table.verticalScrollBar().value() == table_position
    assert QApplication.focusWidget() is restored_table


def test_delete_sample_and_spt_save_keeps_view_while_completion_dialog_is_open(
    qtbot, monkeypatch, tmp_path,
) -> None:
    project = create_empty_project()
    project.folder = tmp_path
    project.boreholes["ZK1"] = Borehole(
        prefix="ZK1", folder=tmp_path, hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "20"]), is_new=True,
        tests={
            "o": [Record(["8.4", "8.8", "ZK1-1"])],
            "q": [Record(["8.95", "9.25", "12"])],
        },
    )
    SaveService(project).save()
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "_project", create_empty_project()))
    window._project = load_project(tmp_path)
    hole = window._project.boreholes["ZK1"]
    window._load_current_borehole(hole)
    window._refresh_borehole_list()
    page = window._test_data_page
    window._tabs.setCurrentWidget(page)
    window.show()
    window.activateWindow()
    table = page._sections["o"]._table
    table.setCurrentIndex(table.model().index(0, 0))
    table.setFocus()
    qtbot.wait(50)
    monkeypatch.setattr(page, "_confirm_sample_deletion", lambda *_: QMessageBox.StandardButton.No)
    page._sections["o"]._delete_row(0)
    assert not hole.tests["o"] and not hole.tests["q"]

    observed = []
    scroll_movements = []
    page._scroll.verticalScrollBar().valueChanged.connect(scroll_movements.append)
    position = page.scroll_position()

    def inspect_completion_dialog():
        qtbot.wait(50)
        dialog = QApplication.activeModalWidget()
        observed.append((dialog.windowTitle(), page.scroll_position(), page._sections["o"]._table is table))
        dialog.accept()

    def save_now(operation, on_success, _on_error):
        result = operation()
        QTimer.singleShot(0, inspect_completion_dialog)
        on_success(result)
        return True

    monkeypatch.setattr(window, "_start_task", save_now)
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    window._save_data()
    qtbot.wait(50)

    assert observed == [("保存完成", position, True)]
    assert all(value == position for value in scroll_movements)
    assert page.scroll_position() == position
    assert not (tmp_path / "ZK1.-o").exists()
    assert not (tmp_path / "ZK1.-q").exists()
    assert not hole.dirty
