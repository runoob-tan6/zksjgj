from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

import borehole.ui.main_window as main_window_module
from borehole.application.project_service import create_empty_project, load_project
from borehole.application.save_service import SaveService
from borehole.application.undo_manager import BoreholeSnapshot
from borehole.domain.enums import HoleType
from borehole.domain.models import Borehole, MainFileData
from borehole.domain.models import TestRecord as Record
from borehole.ui.main_window import MainWindow
from borehole.ui.test_data_page import TestDataPage as DataPage
from borehole.ui.test_data_page import TestRecordModel as RecordModel
from borehole.ui.test_data_page import TestSection as Section


def _hole() -> Borehole:
    return Borehole(
        prefix="ZK1",
        folder=Path("."),
        hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "20"]),
        tests={
            "o": [
                Record(["1.0", "1.4", "ZK1-1"]),
                Record(["4.0", "4.4", "ZK1-2"]),
                Record(["6.0", "6.4", "ZK1-3"]),
                Record(["8.0", "8.4", "ZK1-4"]),
            ],
            "q": [
                Record(["1.55", "1.85", "7"]),
                Record(["4.55", "4.85", "7"]),
                Record(["6.55", "6.85", "9"]),
                Record(["8.55", "8.85", "9"]),
            ],
        },
    )


def _page(qtbot, hole: Borehole) -> DataPage:
    page = DataPage()
    qtbot.addWidget(page)
    page.load_borehole(hole)
    return page


@pytest.mark.parametrize(("suffix", "end"), [("n", "10.4"), ("m", "13.4"), ("o", "8.8"), ("q", "8.7")])
def test_start_depth_updates_existing_end_and_allows_custom_end(qtbot, suffix, end) -> None:
    model = RecordModel(suffix)
    model.load([Record(["1.0", "3.0", "custom"])])
    assert model.setData(model.index(0, 0), "8.4")
    assert model.records[0].values == ["8.4", end, "custom"]
    assert model.setData(model.index(0, 1), "15.25")
    assert model.records[0].values[1] == "15.25"
    assert model.setData(model.index(0, 0), "9.4")
    assert float(model.records[0].values[1]) == pytest.approx(float(end) + 1)


@pytest.mark.parametrize("value", ["", "abc", "NaN", "Infinity"])
def test_invalid_start_does_not_overwrite_end(qtbot, value) -> None:
    model = RecordModel("n")
    model.load([Record(["1", "3", "0.5"])])
    assert model.setData(model.index(0, 0), value)
    assert model.records[0].values[1:] == ["3", "0.5"]


@pytest.mark.parametrize(("suffix", "end"), [("n", "3.125"), ("m", "6.125"), ("o", "1.525")])
def test_empty_row_fills_end_without_rounding_depth(qtbot, suffix, end) -> None:
    model = RecordModel(suffix)
    model.add_record()
    assert model.setData(model.index(0, 0), "1.125")
    assert model.records[0].values[:2] == ["1.125", end]


def test_new_sample_generates_precise_spt_depths_with_empty_count(qtbot) -> None:
    hole = _hole()
    page = _page(qtbot, hole)
    sample = page._sections["o"]
    sample._add()
    sample._model.setData(sample._model.index(4, 0), "8.4")
    assert hole.tests["o"][4].values == ["8.4", "8.8", "ZK1-5"]
    assert hole.tests["q"][4].values == ["8.95", "9.25", ""]
    sample._model.setData(sample._model.index(4, 1), "8.825")
    assert hole.tests["q"][4].values == ["8.975", "9.275", ""]


def test_empty_imported_sample_gets_one_spt_on_first_depth_edit(qtbot) -> None:
    hole = _hole()
    hole.tests["o"].insert(1, Record(["", "", "ZK1-5"]))
    page = _page(qtbot, hole)
    sample = page._sections["o"]._model
    sample.setData(sample.index(1, 0), "2")
    sample.setData(sample.index(1, 0), "2.1")
    assert len(hole.tests["q"]) == 5
    assert hole.tests["q"][1].values == ["2.65", "2.95", ""]


@pytest.mark.parametrize("row", [0, 1, 4])
def test_inserting_sample_renumbers_and_inserts_matching_spt(qtbot, row) -> None:
    hole = _hole()
    original_spts = list(hole.tests["q"])
    page = _page(qtbot, hole)
    sample = page._sections["o"]
    sample._insert_and_select(row)
    assert [record.values[2] for record in hole.tests["o"]] == [f"ZK1-{i}" for i in range(1, 6)]
    assert len(hole.tests["q"]) == 5
    assert hole.tests["q"][row].values == ["", "", ""]
    assert [record for i, record in enumerate(hole.tests["q"]) if i != row] == original_spts
    sample._model.setData(sample._model.index(row, 0), "2")
    assert hole.tests["q"][row].values == ["2.55", "2.85", ""]


def test_deleted_spt_stays_deleted_without_shifting_other_pairs(qtbot) -> None:
    hole = _hole()
    page = _page(qtbot, hole)
    page._sections["q"]._delete_row(1)
    page.load_borehole(hole)
    sample = page._sections["o"]
    sample._model.setData(sample._model.index(1, 0), "4.1")
    assert len(hole.tests["q"]) == 3
    sample._model.setData(sample._model.index(2, 0), "6.1")
    assert hole.tests["q"][1].values == ["6.65", "6.95", "9"]
    sample._insert_and_select(1)
    sample._model.setData(sample._model.index(1, 0), "2")
    assert hole.tests["q"][1].values == ["2.55", "2.85", ""]
    assert hole.tests["q"][2].values == ["6.65", "6.95", "9"]


def test_custom_spt_and_sample_id_survive_later_edits(qtbot) -> None:
    hole = _hole()
    page = _page(qtbot, hole)
    spt = page._sections["q"]._model
    spt.setData(spt.index(0, 0), "2")
    spt.setData(spt.index(0, 1), "2.6")
    spt.setData(spt.index(0, 2), "12")
    sample = page._sections["o"]
    sample._model.setData(sample._model.index(0, 0), "1.1")
    assert hole.tests["q"][0].values == ["2.0", "2.6", "12"]
    sample._model.setData(sample._model.index(0, 2), "CUSTOM")
    sample._insert_and_select(0)
    assert hole.tests["o"][1].values[2] == "CUSTOM"


def test_sample_delete_removes_only_its_spt_and_renumbers(qtbot, monkeypatch) -> None:
    hole = _hole()
    page = _page(qtbot, hole)
    prompts = []

    def confirm(sample, spt):
        prompts.append((sample, spt))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(page, "_confirm_sample_deletion", confirm)
    page._sections["q"]._delete_row(0)
    sample = page._sections["o"]
    sample._table.selectRow(0)
    sample._delete()
    assert [record.values[2] for record in hole.tests["o"]] == ["ZK1-1", "ZK1-2", "ZK1-3"]
    assert len(hole.tests["q"]) == 3
    assert not prompts
    sample._delete_row(1)
    assert len(prompts) == 1
    assert [record.values[2] for record in hole.tests["o"]] == ["ZK1-1", "ZK1-2"]
    assert [record.values[0] for record in hole.tests["q"]] == ["4.55", "8.55"]


def test_load_does_not_generate_missing_or_overwrite_custom_legacy_spts(qtbot) -> None:
    hole = _hole()
    hole.tests["q"].pop(1)
    hole.tests["q"][0].values = ["2", "3", "12"]
    page = _page(qtbot, hole)
    sample = page._sections["o"]._model
    sample.setData(sample.index(1, 0), "4.1")
    sample.setData(sample.index(2, 0), "6.1")
    assert [record.values for record in hole.tests["q"]] == [
        ["2", "3", "12"], ["6.65", "6.95", "9"], ["8.55", "8.85", "9"],
    ]


def test_standalone_section_renumbers_without_nested_undo(qtbot) -> None:
    changes = []
    section = Section("o", lambda *_: "token", changes.append)
    qtbot.addWidget(section)
    hole = _hole()
    section.load_borehole(hole)
    section._insert_and_select(1)
    assert changes == ["token"]
    assert [record.values[2] for record in hole.tests["o"]] == [f"ZK1-{i}" for i in range(1, 6)]


def test_pairing_undo_redo_and_save_reload(qtbot, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "_project", create_empty_project()))
    hole = _hole()
    hole.folder = tmp_path
    hole.is_new = True
    window._project = create_empty_project()
    window._project.folder = tmp_path
    window._project.boreholes[hole.prefix] = hole
    window._refresh_borehole_list()
    window._load_current_borehole(hole)
    window._select_in_tree(hole.prefix)
    page = window._test_data_page
    page._sections["o"]._insert_and_select(1)
    manager = window._get_undo_manager(hole)
    assert len(manager.undo_stack) == 1
    window._undo()
    assert len(hole.tests["o"]) == len(hole.tests["q"]) == 4
    window._redo()
    assert len(hole.tests["o"]) == len(hole.tests["q"]) == 5
    sample = page._sections["o"]._model
    sample.setData(sample.index(1, 0), "2")
    assert {"o", "q"} <= hole.dirty_suffixes
    assert len(manager.undo_stack) == 2
    window._undo()
    assert hole.tests["q"][1].values == ["", "", ""]
    window._redo()
    assert hole.tests["q"][1].values == ["2.55", "2.85", ""]
    page._sections["q"]._delete_row(2)
    window._undo()
    assert len(hole.tests["q"]) == 5
    window._redo()
    sample = page._sections["o"]._model
    sample.setData(sample.index(2, 0), "4.1")
    assert len(hole.tests["q"]) == 4
    SaveService(window._project).save()
    reloaded = load_project(tmp_path).boreholes["ZK1"]
    assert [record.values for record in reloaded.tests["o"]] == [record.values for record in hole.tests["o"]]
    assert [record.values[:2] for record in reloaded.tests["q"]] == [
        record.values[:2] for record in hole.tests["q"]
    ]
    page.load_borehole(reloaded)
    sample = page._sections["o"]._model
    sample.setData(sample.index(2, 0), "4.2")
    sample.setData(sample.index(3, 0), "6.1")
    assert len(reloaded.tests["q"]) == 4
    assert reloaded.tests["q"][2].values == ["6.65", "6.95", "9"]


def test_custom_pair_link_survives_snapshot_restore(qtbot, monkeypatch) -> None:
    hole = _hole()
    page = _page(qtbot, hole)
    monkeypatch.setattr(page, "_confirm_sample_deletion", lambda *_: QMessageBox.StandardButton.No)
    spt = page._sections["q"]._model
    spt.setData(spt.index(0, 0), "2")
    spt.setData(spt.index(0, 1), "3")
    snapshot = BoreholeSnapshot.capture(hole)
    page._sections["o"]._delete_row(0)
    snapshot.restore(hole)
    page.load_borehole(hole)
    assert hole.tests["q"][0].values == ["2.0", "3.0", "7"]
    page._sections["o"]._insert_and_select(0)
    assert hole.tests["q"][0].values == ["", "", ""]
    assert hole.tests["q"][1].values == ["2.0", "3.0", "7"]
    page._sections["o"]._delete_row(1)
    assert len(hole.tests["q"]) == 4
    assert hole.tests["q"][1].values == ["4.55", "4.85", "7"]


@pytest.mark.parametrize("toolbar", [False, True])
@pytest.mark.parametrize("choice", [
    QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No, QMessageBox.StandardButton.Cancel,
])
def test_sample_deletion_choice_is_one_undoable_change(qtbot, monkeypatch, toolbar, choice) -> None:
    hole = _hole()
    changes = []
    page = DataPage(
        lambda borehole, _label: BoreholeSnapshot.capture(borehole),
        lambda before: changes.append((before, BoreholeSnapshot.capture(hole))),
    )
    qtbot.addWidget(page)
    page.load_borehole(hole)
    sample = page._sections["o"]
    sample._insert_and_select(1)
    sample._model.setData(sample._model.index(1, 0), "2")
    spt_model = page._sections["q"]._model
    spt_model.setData(spt_model.index(1, 2), "13")
    changes.clear()
    original_samples = [list(record.values) for record in hole.tests["o"]]
    original_spts = [list(record.values) for record in hole.tests["q"]]
    notifications = []
    page.data_changed.connect(notifications.append)

    def confirm(record, spt):
        assert record is hole.tests["o"][1]
        assert spt is hole.tests["q"][1]
        assert len(hole.tests["o"]) == len(hole.tests["q"]) == 5
        return choice

    monkeypatch.setattr(page, "_confirm_sample_deletion", confirm)
    if toolbar:
        sample._table.selectRow(1)
        sample._delete()
    else:
        sample._delete_row(1)

    if choice == QMessageBox.StandardButton.Cancel:
        assert not changes
        assert not notifications
        assert [record.values for record in hole.tests["o"]] == original_samples
        assert [record.values for record in hole.tests["q"]] == original_spts
        return

    assert len(changes) == 1
    assert [record.values[2] for record in hole.tests["o"]] == [f"ZK1-{i}" for i in range(1, 5)]
    expected_spts = original_spts if choice == QMessageBox.StandardButton.Yes else original_spts[:1] + original_spts[2:]
    assert [record.values for record in hole.tests["q"]] == expected_spts
    assert ("q" in notifications) == (choice == QMessageBox.StandardButton.No)
    before, after = changes[0]
    before.restore(hole)
    page.load_borehole(hole)
    assert [record.values for record in hole.tests["o"]] == original_samples
    assert [record.values for record in hole.tests["q"]] == original_spts
    after.restore(hole)
    page.load_borehole(hole)
    assert len(hole.tests["o"]) == 4
    assert [record.values for record in hole.tests["q"]] == expected_spts
    if choice == QMessageBox.StandardButton.Yes:
        sample = page._sections["o"]
        sample._model.setData(sample._model.index(1, 0), "4.1")
        sample._insert_and_select(1)
        sample._model.setData(sample._model.index(1, 0), "2.1")
        assert hole.tests["q"][1].values == ["2.55", "2.85", "13"]
        assert hole.tests["q"][3].values == ["4.65", "4.95", "7"]


@pytest.mark.parametrize("action", ["default", "keep", "delete", "cancel", "escape", "close"])
def test_sample_deletion_dialog_buttons_and_safe_default(qtbot, action) -> None:
    hole = _hole()
    page = _page(qtbot, hole)
    checks = []

    def respond():
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, QMessageBox):
            return
        checks.append({
            "text": dialog.text(),
            "default": dialog.standardButton(dialog.defaultButton()),
            "escape": dialog.standardButton(dialog.escapeButton()),
            "buttons": [dialog.button(button).text() for button in (
                QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No, QMessageBox.StandardButton.Cancel,
            )],
        })
        if action == "default":
            qtbot.keyClick(dialog, Qt.Key.Key_Return)
        elif action == "escape":
            qtbot.keyClick(dialog, Qt.Key.Key_Escape)
        elif action == "close":
            dialog.close()
        else:
            button = {
                "keep": QMessageBox.StandardButton.Yes,
                "delete": QMessageBox.StandardButton.No,
                "cancel": QMessageBox.StandardButton.Cancel,
            }[action]
            dialog.button(button).click()

    QTimer.singleShot(0, respond)
    result = page._confirm_sample_deletion(hole.tests["o"][0], hole.tests["q"][0])
    expected = {
        "default": QMessageBox.StandardButton.Yes,
        "keep": QMessageBox.StandardButton.Yes,
        "delete": QMessageBox.StandardButton.No,
        "cancel": QMessageBox.StandardButton.Cancel,
        "escape": QMessageBox.StandardButton.Cancel,
        "close": QMessageBox.StandardButton.Cancel,
    }[action]
    assert result == expected
    assert len(checks) == 1
    assert checks[0]["default"] == QMessageBox.StandardButton.Yes
    assert checks[0]["escape"] == QMessageBox.StandardButton.Cancel
    assert checks[0]["buttons"] == ["保留标贯", "同时删除标贯", "取消"]
    assert all(value in checks[0]["text"] for value in ("ZK1-1", "1.55", "1.85", "7"))


def test_kept_spt_survives_save_reload_and_later_sample_deletion(qtbot, monkeypatch, tmp_path) -> None:
    hole = _hole()
    hole.folder = tmp_path
    hole.is_new = True
    project = create_empty_project()
    project.folder = tmp_path
    project.boreholes[hole.prefix] = hole
    original_spts = [list(record.values) for record in hole.tests["q"]]
    page = _page(qtbot, hole)
    page.data_changed.connect(hole.mark_dirty)
    monkeypatch.setattr(page, "_confirm_sample_deletion", lambda *_: QMessageBox.StandardButton.Yes)
    page._sections["o"]._delete_row(1)
    SaveService(project).save()

    reloaded = load_project(tmp_path).boreholes[hole.prefix]
    assert len(reloaded.tests["o"]) == 3
    assert [record.values for record in reloaded.tests["q"]] == original_spts
    page.load_borehole(reloaded)
    monkeypatch.setattr(page, "_confirm_sample_deletion", lambda *_: QMessageBox.StandardButton.No)
    page._sections["o"]._delete_row(1)
    assert [record.values for record in reloaded.tests["q"]] == [
        original_spts[0], original_spts[1], original_spts[3],
    ]
