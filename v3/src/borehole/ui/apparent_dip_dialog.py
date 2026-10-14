"""视倾角计算对话框。"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QLocale, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..domain.apparent_dip import (
    AngleRange,
    ApparentDipResult,
    DipSide,
    calculate_apparent_dip,
)


class _AngleSpin(QDoubleSpinBox):
    def __init__(self, maximum: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLocale(QLocale.c())
        self.setRange(0.0, maximum)
        self.setDecimals(2)
        self.setSingleStep(1.0)
        self.setKeyboardTracking(False)
        self.setSuffix("°")
        self.setMinimumWidth(110)
        if maximum == 360:
            self.setToolTip("方位角：北0°、东90°、南180°、西270°；360°等同0°")

    def number(self) -> float:
        text = self.lineEdit().text().strip().removesuffix(self.suffix()).strip()
        value, valid = self.locale().toDouble(text)
        if not valid or not self.minimum() <= value <= self.maximum():
            raise ValueError("请填写有效的角度数值")
        return value

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


class _RangeInput(QWidget):
    """固定值/范围输入。"""

    changed = Signal()

    def __init__(self, maximum: float, circular: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mode = QComboBox()
        self.mode.addItems(["固定值", "范围"])
        self.start = _AngleSpin(maximum)
        self.end = _AngleSpin(maximum)
        self._end_label = QLabel("至")
        self.cross_north = QCheckBox("跨越0°")
        self._circular = circular
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in (self.mode, self.start, self._end_label, self.end, self.cross_north):
            layout.addWidget(widget)
        layout.addStretch()
        self.mode.currentIndexChanged.connect(self._toggle_range)
        for spin in (self.start, self.end):
            spin.lineEdit().textChanged.connect(lambda _text: self.changed.emit())
            spin.valueChanged.connect(lambda _value: self.changed.emit())
        self.cross_north.toggled.connect(lambda _checked: self.changed.emit())
        self._toggle_range(0)

    def _toggle_range(self, index: int) -> None:
        visible = index == 1
        self._end_label.setVisible(visible)
        self.end.setVisible(visible)
        self.cross_north.setVisible(visible and self._circular)
        self.changed.emit()

    def value(self) -> AngleRange:
        start = self.start.number()
        if self.mode.currentIndex() == 0:
            return AngleRange(start, start)
        end = self.end.number()
        if self._circular and self.cross_north.isChecked():
            if start <= end:
                raise ValueError("跨越0°时，起点应大于终点，例如350°至10°")
            if start == 360:
                raise ValueError("跨越0°的起点请使用小于360°的方位")
            end += 360
        result = AngleRange(start, end)
        if self._circular and end - start > 180:
            raise ValueError("方位范围跨度不能超过180°")
        return result


@dataclass(frozen=True)
class _SectionWidgets:
    name: QLineEdit
    azimuth: _AngleSpin


class ApparentDipDialog(QDialog):
    """结构化输入的视倾角计算器。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("视倾角计算")
        self.setMinimumSize(760, 600)
        self.resize(850, 680)
        self._results: list[tuple[str, float, ApparentDipResult]] = []
        self._report = ""
        self._angle_editors: dict[QObject, _AngleSpin] = {}
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("视倾角计算")
        title.setProperty("class", "title")
        layout.addWidget(title)

        attitude_layout = QFormLayout()
        self._input_mode = QComboBox()
        self._input_mode.addItems(["按走向输入", "按倾向输入"])
        self._strike = _RangeInput(360.0, circular=True)
        self._azimuth_label = QLabel("走向：")
        self._side = QComboBox()
        self._side.addItem("顺时针侧（走向 + 90°）", DipSide.CLOCKWISE)
        self._side.addItem("逆时针侧（走向 - 90°）", DipSide.COUNTERCLOCKWISE)
        self._dip = _RangeInput(90.0)
        self._register_angle_editors(self._strike)
        self._register_angle_editors(self._dip)
        self._derived = QLabel()
        self._derived.setWordWrap(True)
        attitude_layout.addRow("产状输入：", self._input_mode)
        attitude_layout.addRow(self._azimuth_label, self._strike)
        attitude_layout.addRow("倾向侧：", self._side)
        attitude_layout.addRow("真倾角：", self._dip)
        attitude_layout.addRow("对应方位：", self._derived)
        layout.addLayout(attitude_layout)

        section_toolbar = QHBoxLayout()
        section_toolbar.addWidget(QLabel("剖面方向"))
        section_toolbar.addStretch()
        self._add = QPushButton()
        self._add.setAutoDefault(False)
        self._add.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self._add.setToolTip("添加剖面")
        self._add.setAccessibleName("添加剖面")
        self._remove = QPushButton()
        self._remove.setAutoDefault(False)
        self._remove.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self._remove.setToolTip("移除选中的剖面")
        self._remove.setAccessibleName("移除选中的剖面")
        section_toolbar.addWidget(self._add)
        section_toolbar.addWidget(self._remove)
        layout.addLayout(section_toolbar)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["剖面名称", "方位角", "视倾角", "视倾向"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setColumnWidth(0, 150)
        self._table.setColumnWidth(1, 130)
        self._table.setColumnWidth(2, 160)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._sections: list[_SectionWidgets] = []
        layout.addWidget(self._table, 1)

        self._warnings = QTextEdit()
        self._warnings.setReadOnly(True)
        self._warnings.setMaximumHeight(90)
        self._warnings.setPlaceholderText("计算提示")
        layout.addWidget(self._warnings)
        self._error = QLabel()
        self._error.setWordWrap(True)
        layout.addWidget(self._error)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setText("关闭")
            close_button.setAutoDefault(False)
        self._calculate = QPushButton("计算")
        self._copy = QPushButton("复制结果")
        self._copy.setAutoDefault(False)
        self._copy.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        buttons.addButton(self._calculate, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self._copy, QDialogButtonBox.ButtonRole.ActionRole)
        self._calculate.setDefault(True)
        self._calculate.clicked.connect(self.calculate)
        self._copy.clicked.connect(self.copy_results)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._input_mode.currentIndexChanged.connect(self._input_mode_changed)
        self._strike.changed.connect(self._invalidate)
        self._dip.changed.connect(self._invalidate)
        self._side.currentIndexChanged.connect(self._invalidate)
        self._add.clicked.connect(self.add_section)
        self._remove.clicked.connect(self.remove_section)
        self._table.currentCellChanged.connect(self._update_remove_button)
        self.add_section("横剖面", 0)
        self.add_section("纵剖面", 90)
        self._invalidate()

    def _input_mode_changed(self) -> None:
        direction_input = self._input_mode.currentIndex() == 1
        self._azimuth_label.setText("倾向：" if direction_input else "走向：")
        self._side.setEnabled(not direction_input)
        self._invalidate()

    def _register_angle_editors(self, range_input: _RangeInput) -> None:
        for spin in (range_input.start, range_input.end):
            self._register_angle_spin(spin)

    def _register_angle_spin(self, spin: _AngleSpin) -> None:
        for widget in (spin, spin.lineEdit()):
            widget.installEventFilter(self)
            self._angle_editors[widget] = spin

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched in self._angle_editors and isinstance(event, QKeyEvent):
            if event.key() in (
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
            ) and event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                if event.type() == QEvent.Type.KeyPress:
                    spin = self._angle_editors[watched]
                    try:
                        spin.number()
                    except ValueError:
                        pass
                    else:
                        spin.interpretText()
                    self.calculate()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def add_section(self, name: str | bool = "", azimuth: float = 0) -> None:
        if not isinstance(name, str) or not name:
            name = f"剖面{len(self._sections) + 1}"
        row = self._table.rowCount()
        self._table.insertRow(row)
        name_widget = QLineEdit(name)
        azimuth_widget = _AngleSpin(360)
        azimuth_widget.setValue(azimuth)
        self._table.setCellWidget(row, 0, name_widget)
        self._table.setCellWidget(row, 1, azimuth_widget)
        self._table.setRowHeight(row, 38)
        for column in (2, 3):
            self._table.setItem(row, column, QTableWidgetItem())
        self._sections.append(_SectionWidgets(name_widget, azimuth_widget))
        name_widget.textChanged.connect(self._invalidate)
        azimuth_widget.lineEdit().textChanged.connect(self._invalidate)
        azimuth_widget.valueChanged.connect(self._invalidate)
        self._register_angle_spin(azimuth_widget)
        self._table.setCurrentCell(row, 0)
        self._invalidate()

    def remove_section(self) -> None:
        row = self._table.currentRow()
        if len(self._sections) <= 1 or row < 0:
            return
        section = self._sections.pop(row)
        for widget in (section.azimuth, section.azimuth.lineEdit()):
            widget.removeEventFilter(self)
            self._angle_editors.pop(widget, None)
        self._table.removeRow(row)
        self._invalidate()

    def _update_remove_button(self) -> None:
        self._remove.setEnabled(len(self._sections) > 1 and self._table.currentRow() >= 0)

    def _set_result_text(self, row: int, column: int, text: str) -> None:
        item = self._table.item(row, column)
        if item is not None:
            item.setText(text)
            item.setToolTip(text)

    def _inputs(self) -> tuple[AngleRange, DipSide, AngleRange]:
        azimuth = self._strike.value()
        dip = self._dip.value()
        if self._input_mode.currentIndex() == 1:
            strike = AngleRange(azimuth.start - 90, azimuth.end - 90)
            side = DipSide.CLOCKWISE
        else:
            strike = azimuth
            side = DipSide.CLOCKWISE if self._side.currentIndex() == 0 else DipSide.COUNTERCLOCKWISE
        names = [section.name.text().strip() for section in self._sections]
        if any(not name for name in names):
            raise ValueError("请填写剖面名称")
        if len(names) != len(set(names)):
            raise ValueError("剖面名称不能重复")
        for section in self._sections:
            section.azimuth.number()
        return strike, side, dip

    @staticmethod
    def _azimuth_text(angles: AngleRange) -> str:
        if angles.start == angles.end:
            return f"{angles.start % 360:g}°"
        crossing = "（跨越0°）" if angles.start % 360 > angles.end % 360 else ""
        return f"{angles.start % 360:g}° ～ {angles.end % 360:g}°{crossing}"

    def _invalidate(self) -> None:
        self._results.clear()
        self._report = ""
        self._copy.setEnabled(False)
        self._warnings.clear()
        for row in range(self._table.rowCount()):
            self._set_result_text(row, 2, "未计算")
            self._set_result_text(row, 3, "")
        try:
            strike, side, _ = self._inputs()
            offset = 90 if side is DipSide.CLOCKWISE else -90
            direction = AngleRange(strike.start + offset, strike.end + offset)
            self._derived.setText(
                f"走向 {self._azimuth_text(strike)}；倾向 {self._azimuth_text(direction)}"
            )
            if self._input_mode.currentIndex() == 0:
                for index, side_offset in ((0, 90), (1, -90)):
                    side_range = AngleRange(strike.start + side_offset, strike.end + side_offset)
                    label = "顺时针侧" if index == 0 else "逆时针侧"
                    self._side.setItemText(index, f"{label}：{self._azimuth_text(side_range)}")
            self._calculate.setEnabled(True)
            self._error.clear()
        except ValueError as error:
            self._derived.clear()
            self._error.setText(str(error))
            self._calculate.setEnabled(False)
        self._update_remove_button()

    @staticmethod
    def _angle_text(value: float) -> str:
        return "＜0.01°" if 0 < value < 0.01 else f"{value:.2f}°"

    @staticmethod
    def _format_result(result: ApparentDipResult) -> str:
        if result.minimum is None or result.maximum is None:
            return "无法确定"
        if result.is_single_value:
            value = ApparentDipDialog._angle_text(result.minimum)
        else:
            value = (
                f"{ApparentDipDialog._angle_text(result.minimum)} ～ "
                f"{ApparentDipDialog._angle_text(result.maximum)}"
            )
        return value

    def calculate(self) -> None:
        self._invalidate()
        try:
            strike, side, dip = self._inputs()
            results = [
                (
                    section.name.text().strip(),
                    section.azimuth.number(),
                    calculate_apparent_dip(strike, side, dip, section.azimuth.number()),
                )
                for section in self._sections
            ]
            for row, (_, _, result) in enumerate(results):
                self._set_result_text(row, 2, self._format_result(result))
                self._set_result_text(row, 3, result.direction)
            warnings = [
                f"{name}：{warning}"
                for name, _, result in results
                for warning in result.warnings
            ]
            self._warnings.setPlainText("\n".join(warnings) if warnings else "无特殊提示。")
            self._results = results
            self._report = self._build_report(strike, side, dip)
            self._copy.setEnabled(True)
        except ValueError as error:
            self._error.setText(str(error))

    def _build_report(self, strike: AngleRange, side: DipSide, dip: AngleRange) -> str:
        offset = 90 if side is DipSide.CLOCKWISE else -90
        direction = AngleRange(strike.start + offset, strike.end + offset)
        lines = ["视倾角计算结果"]
        lines.extend([
            f"走向：{self._azimuth_text(strike)}",
            f"倾向：{self._azimuth_text(direction)}",
            f"真倾角：{dip.start:g}° ～ {dip.end:g}°" if dip.start != dip.end else f"真倾角：{dip.start:g}°",
        ])
        if strike.start != strike.end or dip.start != dip.end:
            lines.append("范围按走向与倾角的独立组合计算，包含范围内极值。")
        lines.append("公式：β = atan2(sin(α) × |sin(剖面方位 - 走向)|, cos(α))")
        for name, azimuth, result in self._results:
            lines.append(f"{name}（方位{azimuth % 360:g}°）：{self._format_result(result)}；{result.direction}")
            lines.extend(f"  提示：{warning}" for warning in result.warnings)
        return "\n".join(lines)

    def copy_results(self) -> None:
        if self._report:
            QApplication.clipboard().setText(self._report)
