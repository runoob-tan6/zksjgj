"""试验数据编辑页面。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation
from functools import partial
from typing import Any
from uuid import uuid4

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    Qt,
    Signal,
)
from PySide6.QtGui import QIntValidator, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..domain.enums import SUFFIX_NAMES
from ..domain.models import MAIN_INDEX_END_DATE, Borehole, TestRecord
from .format_utils import format_numeric_value

COLUMN_TITLES: dict[str, list[str]] = {
    "e": ["深度", "岩芯获得率", "百分比 (%)"],
    "f": ["深度", "RQD值", "百分比 (%)"],
    "m": ["起始深度", "终止深度", "透水率"],
    "n": ["起始深度", "终止深度", "渗透系数"],
    "o": ["起始深度", "终止深度", "样品编号"],
    "q": ["起始深度", "终止深度", "标贯击数"],
    "l": ["稳定水位", "观测日期", "备注"],
}

NUMERIC_COLUMNS: dict[str, set[int]] = {
    "e": {0, 1},
    "f": {0, 1},
    "m": {0, 1, 2},
    "n": {0, 1, 2},
    "o": {0, 1},
    "q": {0, 1},
    "l": {0},
}
DEFAULT_EF_DEPTH_INTERVAL = 2.0
VISIBLE_TEST_ROWS = 8
MIN_TEST_TABLE_HEIGHT = 300
MIN_TEST_SECTION_HEIGHT = 370
MIN_CORE_SECTION_HEIGHT = 430


class _NoWheelDoubleSpinBox(QDoubleSpinBox):
    """禁用滚轮修改数值，避免编辑增量时误触。"""

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


@dataclass
class _TestDataViewState:
    scroll_position: int
    tables: dict[str, tuple[int, int, int, int]]
    focused_suffix: str | None


def _offset_depth(value: str, offset: str) -> str:
    try:
        depth = Decimal(value.strip())
        if not depth.is_finite():
            return ""
        return format_numeric_value(format((depth + Decimal(offset)).normalize(), "f"))
    except InvalidOperation:
        return ""


def _offset_depth_with_limit(value: str, offset: str, max_depth: float) -> str:
    try:
        start_decimal = Decimal(value.strip())
        limit_decimal = Decimal(str(max_depth))
        if not start_decimal.is_finite() or not limit_decimal.is_finite() or limit_decimal <= 0:
            return _offset_depth(value, offset)
        if start_decimal >= limit_decimal:
            return ""
        end_decimal = start_decimal + Decimal(offset)
        if not end_decimal.is_finite():
            return ""
        if end_decimal <= limit_decimal:
            return format_numeric_value(format(end_decimal.normalize(), "f"))
        return format_numeric_value(format(limit_decimal.normalize(), "f"))
    except InvalidOperation:
        return _offset_depth(value, offset)


def _spt_depths(sample_values: list[str]) -> list[str]:
    end = sample_values[1] if len(sample_values) > 1 else ""
    start = _offset_depth(end, "0.15")
    return [start, _offset_depth(start, "0.3")]


def _same_depths(left: list[str], right: list[str]) -> bool:
    return len(left) >= 2 and all(
        _offset_depth(left[col], "0") == _offset_depth(right[col], "0") for col in (0, 1)
    )


def _format_ef_result(value: str) -> str:
    stripped = str(value).strip()
    if not stripped:
        return ""
    try:
        number = Decimal(stripped)
        if number.is_finite():
            return format(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
    except InvalidOperation:
        pass
    return stripped


def _format_ef_depth(value: str) -> str:
    stripped = str(value).strip()
    if not stripped:
        return ""
    try:
        number = Decimal(stripped)
        if number.is_finite():
            return format(number.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), "f")
    except InvalidOperation:
        pass
    return stripped


class _TrackingDelegate(QStyledItemDelegate):
    """追踪活跃编辑器的 delegate，确保切换时数据不丢失。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active_editor: QWidget | None = None

    def createEditor(
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QWidget:
        editor = super().createEditor(parent, option, index)
        model = index.model()
        if (
            isinstance(editor, QLineEdit)
            and isinstance(model, TestRecordModel)
            and model._suffix in ("e", "f")
            and index.column() == 2
        ):
            editor.setValidator(QIntValidator(0, 100, editor))
        self._active_editor = editor
        return editor

    def setModelData(
        self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        super().setModelData(editor, model, index)
        if self._active_editor is editor:
            self._active_editor = None

    def commit_active_edit(self, view: QTableView) -> None:
        editor = self._active_editor
        if editor:
            model = view.model()
            if model is not None:
                self.setModelData(editor, model, view.currentIndex())
            view.closePersistentEditor(view.currentIndex())
            self._active_editor = None


class TestRecordModel(QAbstractTableModel):
    """单个试验类型的表格模型。"""

    def __init__(self, suffix: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._suffix = suffix
        self._titles = COLUMN_TITLES[suffix]
        self._records: list[TestRecord] = []
        self._loading = False
        self.before_set_data: Callable[[], None] | None = None
        self.after_set_data: Callable[[], None] | None = None
        self.on_depth_changed: Callable[[int, str], None] | None = None
        self.on_depth_rows_changed: Callable[[int], None] | None = None
        self.on_record_changed: Callable[[int, list[str]], None] | None = None
        self.on_record_inserted: Callable[[int], None] | None = None
        self.on_record_removed: Callable[[TestRecord], None] | None = None
        self.depth_interval = DEFAULT_EF_DEPTH_INTERVAL
        self.completion_date: str = ""
        self.borehole_depth: float = 0.0

    def load(self, records: list[TestRecord]) -> None:
        self._loading = True
        self.beginResetModel()
        self._records = records
        self.endResetModel()
        self._loading = False

    def rowCount(self, _parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(self._records)

    def columnCount(self, _parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(self._titles)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return self._titles[section]
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
            if role == Qt.ItemDataRole.ToolTipRole and self._suffix in ("e", "f") and section == 2:
                return "按本行与上一行的深度差计算；第一行从 0 m 开始。"
        if orientation == Qt.Orientation.Vertical:
            if role == Qt.ItemDataRole.DisplayRole:
                return str(section + 1)
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
        return None

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None
        record = self._records[index.row()]
        col = index.column()
        if self._suffix in ("e", "f") and col == 2:
            percentage = self._percentage(index.row())
            if percentage is None:
                return ""
            return f"{percentage}%" if role == Qt.ItemDataRole.DisplayRole else percentage
        if col < len(record.values):
            if self._suffix in ("e", "f") and col == 0:
                return _format_ef_depth(record.values[col])
            if self._suffix in ("e", "f") and col == 1:
                return _format_ef_result(record.values[col])
            return record.values[col]
        return ""

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def _is_numeric_column(self, col: int) -> bool:
        return col in NUMERIC_COLUMNS[self._suffix]

    @property
    def records(self) -> tuple[TestRecord, ...]:
        return tuple(self._records)

    @contextmanager
    def suppress_callbacks(self) -> Iterator[None]:
        previous = self._loading
        self._loading = True
        try:
            yield
        finally:
            self._loading = previous

    def _depth_span(self, row: int) -> Decimal | None:
        try:
            current = Decimal(_format_ef_depth(self._records[row].values[0]))
            previous = Decimal(_format_ef_depth(self._records[row - 1].values[0])) if row else Decimal(0)
        except (IndexError, InvalidOperation):
            return None
        if not current.is_finite() or not previous.is_finite() or current <= previous:
            return None
        return current - previous

    def _percentage(self, row: int) -> str | None:
        span = self._depth_span(row)
        if span is None:
            return None
        try:
            result = Decimal(self._records[row].values[1].strip())
        except (IndexError, InvalidOperation):
            return None
        if not result.is_finite():
            return None
        percentage = (result * 100 / span).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return format(percentage, "f")

    def setData(
        self, index: QModelIndex | QPersistentModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        if self._suffix in ("e", "f") and index.column() == 2:
            text = str(value).strip().removesuffix("%").strip()
            if not text:
                result = ""
            else:
                span = self._depth_span(index.row())
                if span is None:
                    return False
                if not text.isascii() or not text.isdecimal():
                    return False
                percentage = int(text)
                if not 0 <= percentage <= 100:
                    return False
                result = format_numeric_value(
                    format((span * Decimal(percentage) / 100).normalize(), "f")
                )
            changed = self.setData(self.index(index.row(), 1), result)
            if changed:
                self.dataChanged.emit(index, index)
            return changed
        record = self._records[index.row()]
        col = index.column()
        while len(record.values) <= col:
            record.values.append("")
        if self._suffix in ("e", "f") and col == 0:
            formatted = _format_ef_depth(str(value))
        elif self._suffix in ("e", "f") and col == 1:
            formatted = _format_ef_result(str(value))
        else:
            formatted = format_numeric_value(str(value)) if self._is_numeric_column(col) else str(value)
        if record.values[col] == formatted:
            return False
        previous_values = list(record.values)
        if not self._loading and self.before_set_data:
            self.before_set_data()
        record.values[col] = formatted
        self.dataChanged.emit(index, index)
        if self._suffix in ("e", "f") and col in (0, 1):
            percentage_index = self.index(index.row(), 2)
            self.dataChanged.emit(percentage_index, percentage_index)
            if col == 0 and index.row() + 1 < len(self._records):
                next_percentage = self.index(index.row() + 1, 2)
                self.dataChanged.emit(next_percentage, next_percentage)
        # 自动填充和同步（在 after_set_data 之前，确保纳入同一个撤销快照）
        if not self._loading and col == 0 and self.on_depth_changed:
            self.on_depth_changed(index.row(), formatted)
        if not self._loading and col == 0 and self._suffix == "l" and self.completion_date:
            if len(record.values) <= 1 or not record.values[1].strip():
                while len(record.values) < 2:
                    record.values.append("")
                record.values[1] = self.completion_date
        if not self._loading and col == 0 and self._suffix in ("m", "n", "o", "q"):
            offset = {"m": "5", "n": "2", "o": "0.4", "q": "0.3"}[self._suffix]
            end_val = _offset_depth_with_limit(formatted, offset, self.borehole_depth)
            if end_val:
                while len(record.values) < 2:
                    record.values.append("")
                if record.values[1] != end_val:
                    record.values[1] = end_val
                    end_index = self.index(index.row(), 1)
                    self.dataChanged.emit(end_index, end_index)
        if not self._loading and col == 0 and self._suffix == "e" and index.row() == 0:
            self._generate_ef_depth_rows(formatted)
        if not self._loading and col in (0, 1) and self.on_record_changed:
            self.on_record_changed(index.row(), previous_values)
        # 所有自动填充和同步完成后，再提交撤销快照
        if not self._loading and self.after_set_data:
            self.after_set_data()
        return True

    def add_record(self) -> int:
        return self.insert_at(len(self._records))

    def insert_at(self, row: int) -> int:
        row = max(0, min(row, len(self._records)))
        self.beginInsertRows(QModelIndex(), row, row)
        self._records.insert(row, TestRecord(values=[""] * len(self._titles)))
        self.endInsertRows()
        if not self._loading and self.on_record_inserted:
            self.on_record_inserted(row)
        return row

    def remove_record(self, row: int) -> None:
        if 0 <= row < len(self._records):
            self.beginRemoveRows(QModelIndex(), row, row)
            record = self._records.pop(row)
            self.endRemoveRows()
            if not self._loading and self.on_record_removed:
                self.on_record_removed(record)

    def set_depth_interval(self, interval: float) -> bool:
        if self._suffix != "e" or interval <= 0 or self.depth_interval == interval:
            return False
        self.depth_interval = interval
        if self._records:
            self._generate_ef_depth_rows(self._records[0].values[0])
        return True

    def _generate_ef_depth_rows(self, first_depth_str: str) -> None:
        """岩芯获取率：根据第一行深度自动生成后续所有行。"""
        if not self.borehole_depth:
            return
        try:
            first_depth = Decimal(_format_ef_depth(first_depth_str))
            interval = Decimal(str(self.depth_interval))
            borehole_depth = Decimal(_format_ef_depth(str(self.borehole_depth)))
        except (InvalidOperation, ValueError):
            return
        if not first_depth.is_finite() or not interval.is_finite() or interval <= 0:
            return
        if not borehole_depth.is_finite():
            return
        # 计算需要生成的行数
        depths = []
        current = first_depth
        while current < borehole_depth:
            current += interval
            if current > borehole_depth:
                current = borehole_depth
            depths.append(current)
            if current >= borehole_depth:
                break
        if not depths:
            return
        # 重新生成深度时保留每行已有的结果值，只替换深度列。
        old_values = [list(record.values[1:]) for record in self._records]
        while len(self._records) > 1:
            self.beginRemoveRows(QModelIndex(), 1, 1)
            del self._records[1]
            self.endRemoveRows()

        # 更新第一行深度，保留其岩芯获取率。
        first_result = old_values[0] if old_values else []
        first_depth_str = _format_ef_depth(first_depth_str)
        self._records[0].values = [first_depth_str, *first_result]
        self.dataChanged.emit(self.index(0, 0), self.index(0, len(self._titles) - 1))
        if self.on_depth_changed:
            self.on_depth_changed(0, first_depth_str)

        # 添加新行并复用原有行的结果值。
        for row_index, depth in enumerate(depths, start=1):
            row = len(self._records)
            self.beginInsertRows(QModelIndex(), row, row)
            formatted = _format_ef_depth(format(depth, "f"))
            result_values = old_values[row_index] if row_index < len(old_values) else []
            self._records.append(TestRecord(values=[formatted, *result_values]))
            self.endInsertRows()
            if self.on_depth_changed:
                self.on_depth_changed(row, formatted)
        if self.on_depth_rows_changed:
            self.on_depth_rows_changed(len(self._records))


class TestSection(QGroupBox):
    """单个试验类型的编辑区域。"""

    data_changed = Signal(str)

    def __init__(
        self,
        suffix: str,
        begin_change: Callable | None = None,
        end_change: Callable | None = None,
        parent: QWidget | None = None,
    ) -> None:
        title = f".-{suffix} {SUFFIX_NAMES.get(suffix, '')}"
        super().__init__(title, parent)
        # The table's minimum height includes its header and viewport.  Leave
        # extra room for the core-recovery/RQD sections so their eighth row is
        # not visually clipped when a ninth record is present.
        section_height = MIN_CORE_SECTION_HEIGHT if suffix in ("e", "f") else MIN_TEST_SECTION_HEIGHT
        self.setMinimumHeight(section_height)
        self._suffix = suffix
        self._begin_change = begin_change
        self._end_change = end_change
        self._borehole: Borehole | None = None
        self._edit_token: Any = None
        self.on_delete_requested: Callable[[int], None] | None = None
        self.on_delete_rows_requested: Callable[[list[int]], None] | None = None
        self.on_depth_interval_changed: Callable[[float], None] | None = None
        self._model = TestRecordModel(suffix, self)
        self._model.before_set_data = self._on_before_edit
        self._model.after_set_data = self._on_after_edit
        if suffix == "o":
            self._model.on_record_inserted = lambda _row: self._renumber_samples()
            self._model.on_record_removed = lambda _record: self._renumber_samples()
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        btn_add = QPushButton("添加行")
        btn_add.clicked.connect(self._add)
        toolbar.addWidget(btn_add)
        btn_del = QPushButton("删除行")
        btn_del.clicked.connect(self._delete)
        toolbar.addWidget(btn_del)
        if self._suffix in ("e", "f"):
            toolbar.addWidget(QLabel("每行增量"))
            self._depth_interval = _NoWheelDoubleSpinBox()
            self._depth_interval.setRange(0.01, 1000.0)
            self._depth_interval.setDecimals(2)
            self._depth_interval.setSingleStep(0.1)
            self._depth_interval.setValue(DEFAULT_EF_DEPTH_INTERVAL)
            self._depth_interval.setSuffix(" m")
            self._depth_interval.setToolTip("设置 .-e、.-f 深度行之间的增量")
            self._depth_interval.editingFinished.connect(self._apply_depth_interval)
            toolbar.addWidget(self._depth_interval)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._table = QTableView()
        self._table.setObjectName("testDataTable")
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._delegate = _TrackingDelegate(self._table)
        self._table.setItemDelegate(self._delegate)
        # Keep the first eight rows fully visible.  The global header/item
        # padding is applied by the style at polish time and is not reflected
        # reliably by QHeaderView.sizeHint(), so leave a fixed safety margin.
        self._table.setMinimumHeight(MIN_TEST_TABLE_HEIGHT)
        layout.addWidget(self._table, 1)

    def load_borehole(self, borehole: Borehole | None) -> None:
        self.commit_active_edit()
        self._borehole = borehole
        if borehole:
            # 确保 tests 字典中有对应的列表，以便新数据能保存到 borehole 对象
            if self._suffix not in borehole.tests:
                borehole.tests[self._suffix] = []
            self._model.load(borehole.tests[self._suffix])
            self._model.completion_date = borehole.main.normalized_lines()[MAIN_INDEX_END_DATE]
            try:
                self._model.borehole_depth = float(borehole.main.depth)
            except ValueError:
                self._model.borehole_depth = 0.0
        else:
            self._model.load([])
            self._model.completion_date = ""
            self._model.borehole_depth = 0.0

    def commit_active_edit(self) -> None:
        """关闭当前活跃的编辑器，确保数据已提交到模型。"""
        self._delegate.commit_active_edit(self._table)

    def set_depth_changed_callback(self, callback: Callable[[int, str], None]) -> None:
        self._model.on_depth_changed = callback

    def set_depth_interval_callback(self, callback: Callable[[float], None]) -> None:
        self.on_depth_interval_changed = callback

    def set_depth_interval(self, interval: float, *, regenerate: bool = False) -> None:
        if self._suffix not in ("e", "f"):
            return
        self._model.depth_interval = interval
        self._depth_interval.blockSignals(True)
        self._depth_interval.setValue(interval)
        self._depth_interval.blockSignals(False)
        if regenerate and self._suffix == "e" and self._model.records:
            self._model._generate_ef_depth_rows(self._model.records[0].values[0])

    def _apply_depth_interval(self) -> None:
        interval = self._depth_interval.value()
        if self.on_depth_interval_changed:
            self.on_depth_interval_changed(interval)
            return
        if self._suffix != "e" or not self._borehole:
            return
        with self._change("设置 .-e、.-f 每行深度增量"):
            self._model.set_depth_interval(interval)

    def reload_records(self, records: list[TestRecord]) -> None:
        self._model.load(records)

    @contextmanager
    def _change(self, label: str) -> Iterator[None]:
        token = self._begin_change(self._borehole, label) if self._borehole and self._begin_change else None
        try:
            yield
        finally:
            self.data_changed.emit(self._suffix)
            if self._end_change:
                self._end_change(token)

    def _on_before_edit(self) -> None:
        if not self._borehole or not self._begin_change:
            return
        self._edit_token = self._begin_change(self._borehole, f"修改试验数据 .-{self._suffix}")

    def _on_after_edit(self) -> None:
        if self._edit_token and self._end_change:
            self._end_change(self._edit_token)
            self._edit_token = None
        self.data_changed.emit(self._suffix)

    def _add(self) -> None:
        if not self._borehole:
            return
        with self._change(f"新增试验数据 .-{self._suffix} 行"):
            row = self._model.add_record()
        self._table.setCurrentIndex(self._model.index(row, 0))

    def _renumber_samples(self) -> None:
        if self._suffix != "o" or not self._borehole:
            return
        prefix = self._borehole.prefix
        with self._model.suppress_callbacks():
            for row, record in enumerate(self._model.records):
                sample_id = record.values[2] if len(record.values) > 2 else ""
                # Preserve user-defined IDs, but renumber the standard IDs by row.
                if not sample_id or (
                    sample_id.startswith(f"{prefix}-") and sample_id[len(prefix) + 1:].isdigit()
                ):
                    self._model.setData(self._model.index(row, 2), f"{prefix}-{row + 1}")

    def _delete(self) -> None:
        self._delete_rows(self._selected_rows())

    def _selected_rows(self) -> list[int]:
        selection_model = self._table.selectionModel()
        if selection_model is None:
            return []
        return sorted({index.row() for index in selection_model.selectedRows()})

    def _show_context_menu(self, pos: QPoint) -> None:
        index = self._table.indexAt(pos)
        if index.isValid():
            selected_rows = self._selected_rows()
            if index.row() not in selected_rows:
                self._table.selectRow(index.row())
        selected_rows = self._selected_rows()
        menu = QMenu(self)
        if index.isValid():
            row = index.row()
            menu.addAction("在上方添加行", lambda: self._insert_and_select(row))
            menu.addAction("在下方添加行", lambda: self._insert_and_select(row + 1))
            menu.addSeparator()
            if selected_rows:
                label = "删除选中行" if len(selected_rows) > 1 else "删除行"
                menu.addAction(label, lambda rows=selected_rows: self._delete_rows(rows))
        else:
            menu.addAction("添加行", self._add)
            if selected_rows:
                menu.addAction(
                    "删除选中行",
                    lambda rows=selected_rows: self._delete_rows(rows),
                )
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _insert_and_select(self, row: int) -> None:
        if not self._borehole:
            return
        with self._change(f"在上方添加试验数据 .-{self._suffix} 行"):
            inserted = self._model.insert_at(row)
        self._table.setCurrentIndex(self._model.index(inserted, 0))

    def _delete_row(self, row: int) -> None:
        self._delete_rows([row])

    def _delete_rows(self, rows: list[int]) -> None:
        if not self._borehole:
            return
        selected_rows = sorted({row for row in rows if 0 <= row < self._model.rowCount()})
        if not selected_rows:
            return
        if len(selected_rows) == 1 and self.on_delete_requested:
            self.on_delete_requested(selected_rows[0])
            return
        if self.on_delete_rows_requested:
            self.on_delete_rows_requested(selected_rows)
            return
        row_text = "、".join(str(row + 1) for row in selected_rows)
        with self._change(f"删除试验数据 .-{self._suffix} 第{row_text}行"):
            for row in reversed(selected_rows):
                self._model.remove_record(row)


class TestDataPage(QWidget):
    """试验数据编辑页。"""

    data_changed = Signal(str)

    def __init__(
        self,
        begin_change: Callable | None = None,
        end_change: Callable | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._borehole: Borehole | None = None
        self._sections: dict[str, TestSection] = {}
        self._begin_change = begin_change
        self._end_change = end_change
        self._scroll: QScrollArea | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        self._scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        self._container_layout = QVBoxLayout(container)
        self._container_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("试验数据")
        title.setProperty("class", "title")
        self._container_layout.addWidget(title)

        self._grid_area = QWidget()
        self._grid_layout = QGridLayout(self._grid_area)
        self._grid_layout.setSpacing(10)
        self._grid_layout.setColumnStretch(0, 1)
        self._grid_layout.setColumnStretch(1, 1)
        self._container_layout.addWidget(self._grid_area)

        scroll.setWidget(container)

    def scroll_position(self) -> int:
        """Return the outer test-data scroll position for save/reload restore."""
        if self._scroll is None:
            return 0
        return self._scroll.verticalScrollBar().value()

    def restore_scroll_position(self, position: int) -> None:
        if self._scroll is None:
            return
        scrollbar = self._scroll.verticalScrollBar()
        scrollbar.setValue(max(scrollbar.minimum(), min(position, scrollbar.maximum())))

    def capture_view_state(self) -> _TestDataViewState:
        tables = {}
        focused_suffix = None
        focused = QApplication.focusWidget()
        for suffix, section in self._sections.items():
            table = section._table
            current = table.currentIndex()
            tables[suffix] = (
                current.row(), current.column(),
                table.horizontalScrollBar().value(), table.verticalScrollBar().value(),
            )
            if focused is table or (focused is not None and table.isAncestorOf(focused)):
                focused_suffix = suffix
        return _TestDataViewState(self.scroll_position(), tables, focused_suffix)

    def restore_view_state(self, state: _TestDataViewState) -> None:
        for suffix, (row, column, horizontal, vertical) in state.tables.items():
            section = self._sections.get(suffix)
            if section is None:
                continue
            table = section._table
            index = section._model.index(row, column)
            if index.isValid():
                table.setCurrentIndex(index)
            table.horizontalScrollBar().setValue(horizontal)
            table.verticalScrollBar().setValue(vertical)
        focused_section = self._sections.get(state.focused_suffix or "")
        if focused_section is not None and self.isVisible():
            focused_section._table.setFocus(Qt.FocusReason.OtherFocusReason)
        # Restoring table focus can scroll its parent; restore the viewport last.
        self.restore_scroll_position(state.scroll_position)

    def load_borehole(self, borehole: Borehole | None) -> None:
        for section in self._sections.values():
            section.commit_active_edit()
        self._borehole = borehole
        for section in self._sections.values():
            section.setParent(None)
            section.deleteLater()
        self._sections.clear()

        if not borehole:
            return

        for index, suffix in enumerate(borehole.available_test_suffixes()):
            section = TestSection(suffix, self._begin_change, self._end_change)
            section.load_borehole(borehole)
            section.data_changed.connect(self.data_changed)
            if suffix in ("e", "f"):
                section.set_depth_changed_callback(partial(self._sync_ef_depth, suffix))
                section._model.on_depth_rows_changed = partial(self._sync_ef_rows, suffix)
                section.set_depth_interval_callback(self._set_ef_depth_interval)
            row = index // 2
            col = index % 2
            self._grid_layout.addWidget(section, row, col)
            self._sections[suffix] = section
        e_section = self._sections.get("e")
        f_section = self._sections.get("f")
        if e_section and f_section:
            e_section.set_depth_interval(self._inferred_ef_interval(e_section))
            f_section.set_depth_interval(e_section._model.depth_interval)
        self._connect_sample_pairs()

    @staticmethod
    def _inferred_ef_interval(section: TestSection) -> float:
        records = section._model.records
        if len(records) < 3:
            return DEFAULT_EF_DEPTH_INTERVAL
        try:
            first = Decimal(_format_ef_depth(records[0].values[0]))
            second = Decimal(_format_ef_depth(records[1].values[0]))
            interval = second - first
        except (InvalidOperation, IndexError):
            return DEFAULT_EF_DEPTH_INTERVAL
        if (
            first.is_finite() and interval.is_finite()
            and Decimal("0.01") <= interval <= Decimal("1000")
            and interval == interval.quantize(Decimal("0.01"))
        ):
            return float(interval)
        return DEFAULT_EF_DEPTH_INTERVAL

    def _set_ef_depth_interval(self, interval: float) -> None:
        e_section = self._sections.get("e")
        f_section = self._sections.get("f")
        if not e_section or not f_section:
            return
        if e_section._model.depth_interval == interval:
            e_section.set_depth_interval(interval)
            f_section.set_depth_interval(interval)
            return
        records = e_section._model.records
        if not records or not records[0].values[0].strip():
            e_section.set_depth_interval(interval)
            f_section.set_depth_interval(interval)
            return
        try:
            first = Decimal(_format_ef_depth(records[0].values[0]))
            depth = Decimal(_format_ef_depth(str(e_section._model.borehole_depth)))
            if not first.is_finite() or not depth.is_finite() or first >= depth:
                e_section.set_depth_interval(interval)
                f_section.set_depth_interval(interval)
                return
        except InvalidOperation:
            e_section.set_depth_interval(interval)
            f_section.set_depth_interval(interval)
            return
        target_count = 1 + int(((depth - first) / Decimal(str(interval))).to_integral_value(rounding=ROUND_CEILING))
        has_trailing_results = any(
            any(value.strip() for value in record.values[1:])
            for section in (e_section, f_section)
            for record in section._model.records[target_count:]
        )
        if has_trailing_results:
            choice = QMessageBox.question(
                self,
                "调整深度增量",
                "新的深度增量会减少行数，并移除末尾已填写的岩芯获得率或 RQD 值。确定继续吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                e_section.set_depth_interval(e_section._model.depth_interval)
                f_section.set_depth_interval(e_section._model.depth_interval)
                return
        with e_section._change("设置 .-e、.-f 每行深度增量"):
            e_section._model.set_depth_interval(interval)
            e_section.set_depth_interval(interval)
            f_section.set_depth_interval(interval)

    def _connect_sample_pairs(self) -> None:
        sample_section = self._sections.get("o")
        spt_section = self._sections.get("q")
        if not sample_section or not spt_section:
            return
        # Recover unambiguous legacy pairs by depth, never by row number: a
        # missing SPT must not shift the pairing of all subsequent samples.
        for sample in sample_section._model.records:
            if sample.sample_pair_id:
                continue
            depths = _spt_depths(sample.values)
            if not depths[0]:
                continue
            sample.sample_pair_id = uuid4().hex
            matches = [
                spt for spt in spt_section._model.records
                if not spt.sample_pair_id and _same_depths(spt.values, depths)
            ]
            if len(matches) == 1:
                matches[0].sample_pair_id = sample.sample_pair_id
        sample_section._model.on_record_changed = self._sync_sample_depths
        sample_section._model.on_record_inserted = self._insert_sample_pair
        sample_section.on_delete_requested = self._delete_sample
        sample_section.on_delete_rows_requested = self._delete_samples

    def _insert_sample_pair(self, row: int) -> None:
        section = self._sections["o"]
        section._renumber_samples()
        sample = section._model.records[row]
        sample.sample_pair_id = uuid4().hex
        spt_model = self._sections["q"]._model
        following_ids = {
            record.sample_pair_id for record in section._model.records[row + 1:]
            if record.sample_pair_id
        }
        target_row = next(
            (i for i, record in enumerate(spt_model.records) if record.sample_pair_id in following_ids),
            spt_model.rowCount(),
        )
        spt_model.insert_at(target_row)
        spt_model.records[target_row].sample_pair_id = sample.sample_pair_id
        self.data_changed.emit("q")

    def _sync_sample_depths(self, row: int, previous_values: list[str]) -> None:
        sample = self._sections["o"]._model.records[row]
        depths = _spt_depths(sample.values)
        if not depths[0]:
            return
        if not sample.sample_pair_id:
            self._insert_sample_pair(row)
        spt_model = self._sections["q"]._model
        for target_row, record in enumerate(spt_model.records):
            if record.sample_pair_id != sample.sample_pair_id:
                continue
            # A custom SPT interval remains independent of the sample defaults.
            if any(record.values[:2]) and not _same_depths(record.values, _spt_depths(previous_values)):
                return
            with spt_model.suppress_callbacks():
                changed = spt_model.setData(spt_model.index(target_row, 0), depths[0])
                changed = spt_model.setData(spt_model.index(target_row, 1), depths[1]) or changed
            if changed:
                self.data_changed.emit("q")
            return
        # An explicitly removed SPT stays removed when the sample is edited.

    def _confirm_sample_deletion(self, sample: TestRecord, spt: TestRecord) -> int:
        sample_id = sample.values[2] if len(sample.values) > 2 else ""
        values = [*spt.values, "", "", ""]
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle("删除取样")
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setText(
            f"删除取样 {sample_id} 后，是否保留对应的标贯记录？\n\n"
            f"标贯深度：{values[0] or '未填写'} 至 {values[1] or '未填写'} m\n"
            f"标贯击数：{values[2] or '未填写'}"
        )
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
        )
        dialog.button(QMessageBox.StandardButton.Yes).setText("保留标贯")
        dialog.button(QMessageBox.StandardButton.No).setText("同时删除标贯")
        dialog.button(QMessageBox.StandardButton.Cancel).setText("取消")
        dialog.setDefaultButton(QMessageBox.StandardButton.Yes)
        dialog.setEscapeButton(QMessageBox.StandardButton.Cancel)
        return dialog.exec()

    def _delete_sample(self, row: int) -> None:
        self._delete_samples([row])

    def _delete_samples(self, rows: list[int]) -> None:
        section = self._sections["o"]
        self.commit_active_edit()
        selected_rows = sorted({row for row in rows if 0 <= row < section._model.rowCount()})
        if not selected_rows:
            return
        spt_model = self._sections["q"]._model
        decisions: dict[int, tuple[int | None, QMessageBox.StandardButton]] = {}
        for row in selected_rows:
            sample = section._model.records[row]
            spt_row = next(
                (i for i, record in enumerate(spt_model.records)
                 if sample.sample_pair_id and record.sample_pair_id == sample.sample_pair_id),
                None,
            )
            choice = QMessageBox.StandardButton.Yes
            if spt_row is not None:
                choice = self._confirm_sample_deletion(sample, spt_model.records[spt_row])
                if choice not in (QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No):
                    return
            decisions[row] = (spt_row, choice)

        row_text = "、".join(str(row + 1) for row in selected_rows)
        with section._change(f"删除试验数据 .-o 第{row_text}行"):
            for row in reversed(selected_rows):
                section._model.remove_record(row)
            spt_rows = sorted(
                {
                    spt_row
                    for spt_row, choice in decisions.values()
                    if spt_row is not None and choice == QMessageBox.StandardButton.No
                },
                reverse=True,
            )
            for spt_row in spt_rows:
                spt_model.remove_record(spt_row)
            if spt_rows:
                self.data_changed.emit("q")

    def commit_active_edit(self) -> None:
        """提交所有试验数据表格的活跃编辑。"""
        for section in self._sections.values():
            section.commit_active_edit()

    def _sync_ef_depth(self, source_suffix: str, row_index: int, depth: str) -> None:
        if not self._borehole or source_suffix not in ("e", "f"):
            return
        target_suffix = "f" if source_suffix == "e" else "e"
        target_section = self._sections.get(target_suffix)
        if not target_section:
            return
        records = self._borehole.tests.setdefault(target_suffix, [])
        while len(records) <= row_index:
            records.append(TestRecord(values=["", ""]))
        target = records[row_index]
        while len(target.values) < 2:
            target.values.append("")
        if target.values[0] != depth:
            target.values[0] = depth
            self.data_changed.emit(target_suffix)
            target_section.reload_records(records)

    def _sync_ef_rows(self, source_suffix: str, row_count: int) -> None:
        if not self._borehole or source_suffix not in ("e", "f"):
            return
        target_suffix = "f" if source_suffix == "e" else "e"
        target_section = self._sections.get(target_suffix)
        if not target_section:
            return
        records = self._borehole.tests.setdefault(target_suffix, [])
        if len(records) <= row_count:
            return
        del records[row_count:]
        self.data_changed.emit(target_suffix)
        target_section.reload_records(records)
