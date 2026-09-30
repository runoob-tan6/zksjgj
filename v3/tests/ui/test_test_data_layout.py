from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QValidator, QWheelEvent
from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox, QStyleOptionViewItem

from borehole.application.project_service import create_empty_project, load_project
from borehole.application.save_service import SaveService
from borehole.application.undo_manager import BoreholeSnapshot
from borehole.domain.enums import HoleType
from borehole.domain.models import Borehole, MainFileData
from borehole.domain.models import TestRecord as Record
from borehole.infrastructure.file_writer import build_test_file_lines
from borehole.ui.test_data_page import MIN_CORE_SECTION_HEIGHT, VISIBLE_TEST_ROWS
from borehole.ui.test_data_page import TestDataPage as DataPage
from borehole.ui.test_data_page import TestRecordModel as RecordModel
from borehole.ui.test_data_page import TestSection as Section


def test_core_recovery_and_rqd_tables_show_eight_complete_rows(qtbot) -> None:
    app = QApplication.instance()
    assert app is not None
    original_style_sheet = app.styleSheet()
    app.setStyleSheet(
        "QWidget { font-size: 10pt; } "
        "QTableView::item { padding: 4px; } "
        "QHeaderView::section { padding: 8px; }"
    )
    try:
        borehole = Borehole(
            prefix="ZK1",
            folder=Path("."),
            hole_type=HoleType.ZK,
            main=MainFileData(["ZK1", "20"]),
            tests={
                suffix: [Record(["1", "2"]) for _ in range(VISIBLE_TEST_ROWS)]
                for suffix in ("e", "f")
            },
        )
        for suffix in ("e", "f"):
            section = Section(suffix)
            qtbot.addWidget(section)
            section.load_borehole(borehole)
            section.show()
            app.processEvents()
            table = section._table
            assert table.viewport().height() >= VISIBLE_TEST_ROWS * table.rowHeight(0)
            assert section.height() >= MIN_CORE_SECTION_HEIGHT
            assert table.geometry().bottom() <= section.rect().bottom()
    finally:
        app.setStyleSheet(original_style_sheet)


def test_editing_core_recovery_depth_preserves_result_values(qtbot) -> None:
    borehole = Borehole(
        prefix="ZK1",
        folder=Path("."),
        hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "16.2"]),
        tests={
            "e": [
                Record(["6.0", "0.0"]),
                Record(["8.0", "1.40"]),
                Record(["10.0", "1.46"]),
                Record(["12.0", "1.64"]),
                Record(["14.0", "1.80"]),
                Record(["16.2", "2.02"]),
            ],
            "f": [
                Record(["6.0", "0.0"]),
                Record(["8.0", "1.18"]),
                Record(["10.0", "1.30"]),
                Record(["12.0", "1.52"]),
                Record(["14.0", "1.72"]),
                Record(["16.2", "1.98"]),
            ],
        },
    )
    section = Section("e")
    qtbot.addWidget(section)
    section.load_borehole(borehole)

    model = section._model
    assert model.setData(model.index(0, 0), "7.5")

    assert [record.values for record in borehole.tests["e"]] == [
        ["7.5", "0.0"],
        ["9.5", "1.40"],
        ["11.5", "1.46"],
        ["13.5", "1.64"],
        ["15.5", "1.80"],
        ["16.2", "2.02"],
    ]


def test_editing_core_recovery_depth_removes_extra_rqd_rows(qtbot) -> None:
    borehole = Borehole(
        prefix="ZK1",
        folder=Path("."),
        hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "22.2"]),
        tests={
            "e": [Record([str(depth), ""]) for depth in (12, 14, 16, 18, 20, 22, 22.2)],
            "f": [Record([str(depth), f"{index:.2f}"]) for index, depth in enumerate(
                (12, 14, 16, 18, 20, 22, 21.5, 22.2), start=1
            )],
        },
    )
    page = DataPage()
    qtbot.addWidget(page)
    page.load_borehole(borehole)
    page._sections["e"]._model.setData(page._sections["e"]._model.index(0, 0), "12.1")

    assert len(borehole.tests["f"]) == len(borehole.tests["e"])
    assert [record.values[1] for record in borehole.tests["f"]] == [
        "1.00", "2.00", "3.00", "4.00", "5.00", "6.00", "7.00"
    ]


def test_custom_ef_interval_regenerates_and_syncs_results(qtbot, monkeypatch) -> None:
    borehole = Borehole(
        prefix="ZK1",
        folder=Path("."),
        hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "16.2"]),
        tests={
            "e": [Record([str(depth), str(row)]) for row, depth in enumerate((6, 8, 10, 12, 14, 16.2))],
            "f": [Record([str(depth), f"r{row}"]) for row, depth in enumerate((6, 8, 10, 12, 14, 16.2))],
        },
    )
    changes = []
    page = DataPage(
        lambda hole, _label: BoreholeSnapshot.capture(hole),
        lambda before: changes.append((before, BoreholeSnapshot.capture(borehole))),
    )
    qtbot.addWidget(page)
    page.load_borehole(borehole)

    f_control = page._sections["f"]._depth_interval
    assert f_control.value() == page._sections["e"]._depth_interval.value() == 2.0
    confirmations = []
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *_args: confirmations.append(True) or QMessageBox.StandardButton.Yes,
    )
    f_control.setValue(3.5)
    f_control.editingFinished.emit()

    assert [record.values for record in borehole.tests["e"]] == [
        ["6.0", "0"], ["9.5", "1"], ["13.0", "2"], ["16.2", "3"],
    ]
    assert [record.values for record in borehole.tests["f"]] == [
        ["6.0", "r0"], ["9.5", "r1"], ["13.0", "r2"], ["16.2", "r3"],
    ]
    assert page._sections["e"]._depth_interval.value() == 3.5
    assert len(changes) == 1
    assert confirmations == [True]

    page.load_borehole(borehole)
    assert page._sections["e"]._depth_interval.value() == page._sections["f"]._depth_interval.value() == 3.5
    changes[0][0].restore(borehole)
    page.load_borehole(borehole)
    assert len(borehole.tests["e"]) == len(borehole.tests["f"]) == 6
    assert page._sections["e"]._depth_interval.value() == 2.0


def test_rejecting_interval_change_preserves_filled_rows(qtbot, monkeypatch) -> None:
    borehole = Borehole(
        prefix="ZK1",
        folder=Path("."),
        hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "6"]),
        tests={
            "e": [Record([str(depth), str(row)]) for row, depth in enumerate((0, 2, 4, 6))],
            "f": [Record([str(depth), f"r{row}"]) for row, depth in enumerate((0, 2, 4, 6))],
        },
    )
    page = DataPage()
    qtbot.addWidget(page)
    page.load_borehole(borehole)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No)
    page._sections["e"]._depth_interval.setValue(3.0)
    page._sections["e"]._depth_interval.editingFinished.emit()

    assert len(borehole.tests["e"]) == len(borehole.tests["f"]) == 4
    assert page._sections["e"]._depth_interval.value() == page._sections["f"]._depth_interval.value() == 2.0


def test_ef_interval_before_first_depth_does_not_change_borehole(qtbot) -> None:
    borehole = Borehole(
        prefix="ZK1",
        folder=Path("."),
        hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "5"]),
    )
    changes = []
    page = DataPage(lambda *_: "token", changes.append)
    qtbot.addWidget(page)
    page.load_borehole(borehole)
    e_section = page._sections["e"]
    e_section._depth_interval.setValue(1.25)
    e_section._depth_interval.editingFinished.emit()

    assert changes == []
    assert page._sections["f"]._depth_interval.value() == 1.25

    e_section._add()
    assert e_section._model.setData(e_section._model.index(0, 0), "0")
    assert [record.values[0] for record in borehole.tests["e"]] == [
        "0.0", "1.3", "2.5", "3.8", "5.0",
    ]
    assert [record.values[0] for record in borehole.tests["f"]] == [
        "0.0", "1.3", "2.5", "3.8", "5.0",
    ]


@pytest.mark.parametrize("suffix", ("e", "f"))
@pytest.mark.parametrize("focused", (False, True))
@pytest.mark.parametrize("delta", (-120, 120))
@pytest.mark.parametrize("editor_target", (False, True))
def test_ef_interval_ignores_mouse_wheel(
    qtbot, suffix, focused, delta, editor_target,
) -> None:
    borehole = Borehole(
        prefix="ZK1",
        folder=Path("."),
        hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "6"]),
        tests={
            key: [Record([str(depth), "1.00"]) for depth in (0, 2, 4, 6)]
            for key in ("e", "f")
        },
    )
    changes = []
    page = DataPage(lambda *_: "token", changes.append)
    qtbot.addWidget(page)
    page.load_borehole(borehole)
    page.show()
    control = page._sections[suffix]._depth_interval
    target = control.lineEdit() if editor_target else control
    if focused:
        target.setFocus()
    else:
        page._sections[suffix]._table.setFocus()
    QApplication.processEvents()
    assert control.hasFocus() == focused
    before = {
        key: [list(record.values) for record in borehole.tests[key]]
        for key in ("e", "f")
    }
    position = target.rect().center()
    event = QWheelEvent(
        QPointF(position),
        QPointF(target.mapToGlobal(position)),
        QPoint(),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(target, event)
    assert not event.isAccepted()
    assert control.value() == 2.0
    assert control.text() == "2.00 m"
    control.editingFinished.emit()
    assert changes == []
    assert {
        key: [list(record.values) for record in borehole.tests[key]]
        for key in ("e", "f")
    } == before


@pytest.mark.parametrize("suffix", ("e", "f"))
def test_ef_interval_still_accepts_typed_input(qtbot, suffix) -> None:
    borehole = Borehole(
        prefix="ZK1",
        folder=Path("."),
        hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "5"]),
        tests={key: [Record(["0.0", ""])] for key in ("e", "f")},
    )
    page = DataPage()
    qtbot.addWidget(page)
    page.load_borehole(borehole)
    page.show()
    control = page._sections[suffix]._depth_interval
    control.setFocus()
    control.selectAll()
    qtbot.keyClicks(control, "1.25")
    qtbot.keyClick(control, Qt.Key.Key_Return)
    assert control.text() == "1.25 m"
    for key in ("e", "f"):
        assert page._sections[key]._depth_interval.value() == 1.25
        assert [record.values[0] for record in borehole.tests[key]] == [
            "0.0", "1.3", "2.5", "3.8", "5.0",
        ]


def test_ef_percentage_uses_each_depth_span_and_keeps_legacy_values(qtbot) -> None:
    for suffix in ("e", "f"):
        model = RecordModel(suffix)
        model.load([
            Record(["6.0", "0.0"]),
            Record(["8.0", "1.40"]),
            Record(["8.4", "0.20"]),
        ])
        assert model.columnCount() == 3
        assert model.data(model.index(1, 2)) == "70%"
        assert model.data(model.index(2, 2)) == "50%"
        assert model.setData(model.index(1, 2), "75%")
        assert model.records[1].values == ["8.0", "1.50"]
        assert model.data(model.index(1, 2)) == "75%"
        assert model.setData(model.index(2, 2), "25")
        assert model.records[2].values == ["8.4", "0.10"]
        assert model.setData(model.index(0, 2), "50")
        assert model.records[0].values == ["6.0", "3.00"]
        assert model.setData(model.index(1, 1), "1.6")
        assert model.data(model.index(1, 2)) == "80%"
        assert model.setData(model.index(1, 1), "1.33")
        assert model.data(model.index(1, 2)) == "67%"
        assert model.setData(model.index(1, 1), "1.335")
        assert model.records[1].values == ["8.0", "1.34"]
        assert model.data(model.index(0, 1)) == "3.00"
        assert not model.setData(model.index(1, 2), "101")
        assert not model.setData(model.index(1, 2), "75.5")
        assert not model.setData(model.index(1, 2), "bad")
        assert model.records[1].values == ["8.0", "1.34"]


def test_ef_depth_has_one_decimal_in_editor_and_file(qtbot) -> None:
    borehole = Borehole(
        prefix="ZK1",
        folder=Path("."),
        hole_type=HoleType.ZK,
        tests={
            suffix: [Record(["6.24", "1.40"]), Record(["8.26", "0.50"])]
            for suffix in ("e", "f")
        },
    )
    for suffix in ("e", "f"):
        model = RecordModel(suffix)
        model.load(borehole.tests[suffix])
        assert model.data(model.index(0, 0)) == "6.2"
        assert model.setData(model.index(1, 0), "8.26")
        assert model.records[1].values[0] == "8.3"
        assert build_test_file_lines(borehole, suffix) == ["6.2,1.40", "8.3,0.50"]


def test_ef_percentage_requires_positive_depth_span(qtbot) -> None:
    model = RecordModel("e")
    model.load([Record(["0", ""]), Record(["0", "1.0"]), Record(["bad", ""])])
    for row in range(3):
        assert model.data(model.index(row, 2)) == ""
        assert not model.setData(model.index(row, 2), "50")
    assert [record.values for record in model.records] == [
        ["0", ""], ["0", "1.0"], ["bad", ""],
    ]


def test_ef_percentage_editor_accepts_only_integers(qtbot) -> None:
    section = Section("e")
    qtbot.addWidget(section)
    section._model.load([Record(["2", "1"])])
    editor = section._delegate.createEditor(
        section._table.viewport(), QStyleOptionViewItem(), section._model.index(0, 2),
    )
    assert isinstance(editor, QLineEdit)
    assert editor.validator().validate("75", 0)[0] == QValidator.State.Acceptable
    assert editor.validator().validate("75.5", 0)[0] == QValidator.State.Invalid
    assert editor.validator().validate("101", 0)[0] != QValidator.State.Acceptable


def test_ef_percentage_edit_is_undoable_and_survives_save(qtbot, tmp_path) -> None:
    borehole = Borehole(
        prefix="ZK1",
        folder=tmp_path,
        hole_type=HoleType.ZK,
        main=MainFileData(["ZK1", "8"]),
        tests={
            "e": [Record(["6.0", "0.0"]), Record(["8.0", "1.4"])],
            "f": [Record(["6.0", "0.0"]), Record(["8.0", "1.0"])],
        },
        is_new=True,
    )
    changes = []
    page = DataPage(
        lambda hole, _label: BoreholeSnapshot.capture(hole),
        lambda before: changes.append((before, BoreholeSnapshot.capture(borehole))),
    )
    qtbot.addWidget(page)
    page.load_borehole(borehole)
    page.data_changed.connect(borehole.mark_dirty)
    e_model = page._sections["e"]._model
    assert e_model.setData(e_model.index(1, 2), "65")
    assert borehole.tests["e"][1].values == ["8.0", "1.30"]
    assert len(changes) == 1

    project = create_empty_project()
    project.folder = tmp_path
    project.boreholes[borehole.prefix] = borehole
    SaveService(project).save()
    assert (tmp_path / "ZK1.-e").read_text(encoding="utf-8").splitlines()[1] == "8.0,1.30"
    assert (tmp_path / "ZK1.-f").read_text(encoding="utf-8").splitlines()[1] == "8.0,1.00"
    reloaded = load_project(tmp_path).boreholes["ZK1"]
    page.load_borehole(reloaded)
    assert page._sections["e"]._model.data(page._sections["e"]._model.index(1, 2)) == "65%"
    assert page._sections["f"]._model.data(page._sections["f"]._model.index(1, 2)) == "50%"

    changes[0][0].restore(borehole)
    page.load_borehole(borehole)
    assert page._sections["e"]._model.data(page._sections["e"]._model.index(1, 2)) == "70%"
