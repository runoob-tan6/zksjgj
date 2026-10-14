from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import borehole.ui.main_window as main_window_module
from borehole.ui.apparent_dip_dialog import ApparentDipDialog
from borehole.ui.main_window import MainWindow


@pytest.fixture
def dialog(qtbot):
    widget = ApparentDipDialog()
    qtbot.addWidget(widget)
    widget.show()
    return widget


def set_original_example(dialog) -> None:
    dialog._strike.start.setValue(62)
    dialog._strike.end.setValue(65)
    dialog._strike.mode.setCurrentIndex(1)
    dialog._dip.start.setValue(20)
    dialog._dip.end.setValue(25)
    dialog._dip.mode.setCurrentIndex(1)
    dialog._side.setCurrentIndex(1)
    dialog._sections[0].azimuth.setValue(74)
    dialog._sections[1].azimuth.setValue(344)


def test_calculate_original_example_and_copy_full_report(dialog, qtbot) -> None:
    set_original_example(dialog)
    qtbot.mouseClick(dialog._calculate, Qt.MouseButton.LeftButton)
    assert dialog._table.item(0, 2).text() == "3.26° ～ 5.54°"
    assert dialog._table.item(0, 3).text() == "S74°W"
    assert dialog._table.item(1, 2).text() == "19.60° ～ 24.73°"
    assert "332°" in dialog._derived.text()
    assert dialog._copy.isEnabled()
    qtbot.mouseClick(dialog._copy, Qt.MouseButton.LeftButton)
    report = QApplication.clipboard().text()
    assert "62° ～ 65°" in report and "332° ～ 335°" in report
    assert "真倾角：20° ～ 25°" in report
    assert "独立组合" in report and "方位344°" in report


@pytest.mark.parametrize("change", ["angle", "mode", "side", "name", "section", "raw_text"])
def test_input_changes_invalidate_old_results(dialog, change) -> None:
    set_original_example(dialog)
    dialog.calculate()
    assert dialog._report
    if change == "angle":
        dialog._dip.start.setValue(21)
    elif change == "mode":
        dialog._strike.mode.setCurrentIndex(0)
    elif change == "side":
        dialog._side.setCurrentIndex(0)
    elif change == "name":
        dialog._sections[0].name.setText("新剖面")
    elif change == "section":
        dialog._sections[0].azimuth.setValue(75)
    else:
        dialog._dip.start.lineEdit().setText("22°")
    assert not dialog._report
    assert not dialog._copy.isEnabled()
    assert dialog._table.item(0, 2).text() == "未计算"


def test_reversed_range_disables_calculation_inline(dialog) -> None:
    dialog._strike.start.setValue(65)
    dialog._strike.end.setValue(62)
    dialog._strike.mode.setCurrentIndex(1)
    assert not dialog._calculate.isEnabled()
    assert "下限" in dialog._error.text()
    dialog._strike.end.setValue(70)
    assert dialog._calculate.isEnabled()
    assert not dialog._error.text()


def test_empty_and_out_of_range_raw_text_is_not_silently_calculated(dialog) -> None:
    dialog._strike.start.lineEdit().setText("")
    assert not dialog._calculate.isEnabled()
    dialog._strike.start.lineEdit().setText("361°")
    assert not dialog._calculate.isEnabled()
    dialog._strike.start.setValue(62)
    assert dialog._calculate.isEnabled()


def test_north_crossing_requires_explicit_checkbox(dialog) -> None:
    dialog._strike.start.setValue(350)
    dialog._strike.end.setValue(10)
    dialog._strike.mode.setCurrentIndex(1)
    assert not dialog._calculate.isEnabled()
    dialog._strike.cross_north.setChecked(True)
    assert dialog._strike.value().end == 370
    assert dialog._calculate.isEnabled()
    dialog._dip.start.setValue(25)
    dialog.calculate()
    assert "反转" in dialog._table.item(0, 3).text()
    assert "跨越0°" in dialog._report


def test_direction_input_derives_strike_without_editable_side(dialog) -> None:
    dialog._input_mode.setCurrentIndex(1)
    dialog._strike.start.setValue(332)
    dialog._strike.end.setValue(335)
    dialog._strike.mode.setCurrentIndex(1)
    dialog._dip.start.setValue(20)
    dialog._dip.end.setValue(25)
    dialog._dip.mode.setCurrentIndex(1)
    dialog._sections[0].azimuth.setValue(74)
    assert not dialog._side.isEnabled()
    dialog.calculate()
    assert dialog._table.item(0, 2).text() == "3.26° ～ 5.54°"
    assert dialog._table.item(0, 3).text() == "S74°W"


def test_add_remove_sections_and_validate_names(dialog) -> None:
    dialog.add_section("第三剖面", 100)
    assert dialog._table.rowCount() == 3
    dialog._sections[2].name.setText("横剖面")
    assert not dialog._calculate.isEnabled()
    assert "重复" in dialog._error.text()
    dialog._sections[2].name.setText("")
    assert not dialog._calculate.isEnabled()
    dialog._sections[2].name.setText("第三剖面")
    dialog.remove_section()
    assert dialog._table.rowCount() == 2
    dialog._table.setCurrentCell(0, 0)
    dialog.remove_section()
    dialog.remove_section()
    assert dialog._table.rowCount() == 1
    assert not dialog._remove.isEnabled()


def test_vertical_singular_result_is_explicit(dialog) -> None:
    dialog._strike.start.setValue(62)
    dialog._dip.start.setValue(90)
    dialog._sections[0].azimuth.setValue(62)
    dialog.calculate()
    assert dialog._table.item(0, 2).text() == "无法确定"
    assert "直立层" in dialog._warnings.toPlainText()


def test_tiny_nonzero_result_is_not_formatted_as_zero(dialog) -> None:
    dialog._strike.start.setValue(0)
    dialog._dip.start.setValue(0.01)
    dialog._sections[0].azimuth.setValue(0.01)
    dialog.calculate()
    assert dialog._table.item(0, 2).text() == "＜0.01°"


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
@pytest.mark.parametrize("field", ["strike", "dip", "dip_end", "section"])
def test_enter_in_angle_field_calculates_without_adding_section(dialog, qtbot, key, field) -> None:
    set_original_example(dialog)
    spins = {
        "strike": dialog._strike.start,
        "dip": dialog._dip.start,
        "dip_end": dialog._dip.end,
        "section": dialog._sections[0].azimuth,
    }
    spin = spins[field]
    editor = spin.lineEdit()
    editor.setFocus()
    editor.selectAll()
    qtbot.keyClicks(editor, {"strike": "63", "dip": "21", "dip_end": "26", "section": "75"}[field])
    qtbot.keyClick(editor, key)
    assert dialog._table.rowCount() == 2
    assert len(dialog._results) == 2
    assert spin.value() == {"strike": 63, "dip": 21, "dip_end": 26, "section": 75}[field]
    assert dialog._table.item(0, 2).text() != "未计算"
    assert dialog.isVisible()


def test_enter_with_invalid_range_does_not_add_remove_or_close(dialog, qtbot) -> None:
    set_original_example(dialog)
    editor = dialog._dip.start.lineEdit()
    editor.setFocus()
    editor.selectAll()
    qtbot.keyClicks(editor, "30")
    qtbot.keyClick(editor, Qt.Key.Key_Return)
    assert dialog._table.rowCount() == 2
    assert not dialog._results
    assert not dialog._calculate.isEnabled()
    assert dialog.isVisible()
    assert "下限" in dialog._error.text()


def test_add_section_still_works_by_mouse_click(dialog, qtbot) -> None:
    qtbot.mouseClick(dialog._add, Qt.MouseButton.LeftButton)
    assert dialog._table.rowCount() == 3


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
@pytest.mark.parametrize("target", ["editor", "spin"])
@pytest.mark.parametrize("field", ["strike", "dip", "dip_end", "section", "added_section"])
def test_enter_is_consumed_even_if_add_button_is_default(dialog, qtbot, field, target, key) -> None:
    set_original_example(dialog)
    dialog.add_section("附加剖面", 120)
    spins = {
        "strike": dialog._strike.start,
        "dip": dialog._dip.start,
        "dip_end": dialog._dip.end,
        "section": dialog._sections[0].azimuth,
        "added_section": dialog._sections[2].azimuth,
    }
    widget = spins[field].lineEdit() if target == "editor" else spins[field]
    widget.setFocus()
    dialog._add.setDefault(True)
    qtbot.keyClick(widget, key)
    assert dialog._table.rowCount() == 3
    assert len(dialog._results) == 3
    assert dialog.isVisible()


def test_repeated_enter_in_section_field_commits_and_calculates_once_per_press(dialog, qtbot, monkeypatch) -> None:
    set_original_example(dialog)
    editor = dialog._sections[0].azimuth.lineEdit()
    editor.setFocus()
    editor.selectAll()
    qtbot.keyClicks(editor, "173")
    calls = []
    calculate = dialog.calculate

    def counted_calculate():
        calls.append(True)
        calculate()

    monkeypatch.setattr(dialog, "calculate", counted_calculate)
    for _ in range(3):
        qtbot.keyClick(editor, Qt.Key.Key_Return)
    assert len(calls) == 3
    assert dialog._table.rowCount() == 2
    assert dialog._sections[0].azimuth.value() == 173
    assert "方位173°" in dialog._report


def test_tools_menu_opens_calculator_without_loaded_project(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window)
    opened = []

    def execute(self):
        opened.append(self)
        return 0

    monkeypatch.setattr(ApparentDipDialog, "exec", execute)
    menu_actions = window.menuBar().actions()
    tools = menu_actions[2].menu()
    action = next(action for action in tools.actions() if action.text() == "视倾角计算...")
    action.trigger()
    assert len(opened) == 1
    assert not window._project.dirty_boreholes()
    assert not window._project.profile_files
