"""试验数据编辑页面。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import partial
from typing import Any

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
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
    "e": ["深度", "岩芯获得率"],
    "f": ["深度", "RQD值"],
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
SAMPLE_DEPTH_INTERVAL = 2.0


class _TrackingDelegate(QStyledItemDelegate):
    """追踪活跃编辑器的 delegate，确保切换时数据不丢失。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active_editor: QWidget | None = None

    def createEditor(
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QWidget:
        editor = super().createEditor(parent, option, index)
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
        if col < len(record.values):
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

    def setData(
        self, index: QModelIndex | QPersistentModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole:
            return False
        record = self._records[index.row()]
        col = index.column()
        while len(record.values) <= col:
            record.values.append("")
        formatted = format_numeric_value(str(value)) if self._is_numeric_column(col) else str(value)
        if record.values[col] == formatted:
            return False
        if not self._loading and self.before_set_data:
            self.before_set_data()
        record.values[col] = formatted
        self.dataChanged.emit(index, index)
        # 自动填充和同步（在 after_set_data 之前，确保纳入同一个撤销快照）
        if not self._loading and col == 0 and self.on_depth_changed:
            self.on_depth_changed(index.row(), formatted)
        if not self._loading and col == 0 and self._suffix == "l" and self.completion_date:
            if len(record.values) <= 1 or not record.values[1].strip():
                while len(record.values) < 2:
                    record.values.append("")
                record.values[1] = self.completion_date
        if not self._loading and col == 0 and self._suffix == "n":
            try:
                start = float(formatted)
                end_val = format_numeric_value(f"{start + 2:.1f}")
            except ValueError:
                end_val = ""
            if end_val:
                while len(record.values) < 2:
                    record.values.append("")
                if not record.values[1].strip():
                    record.values[1] = end_val
                    end_index = self.index(index.row(), 1)
                    self.dataChanged.emit(end_index, end_index)
        if not self._loading and col == 0 and self._suffix == "e" and index.row() == 0:
            self._generate_ef_depth_rows(formatted)
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
        return row

    def remove_record(self, row: int) -> None:
        if 0 <= row < len(self._records):
            self.beginRemoveRows(QModelIndex(), row, row)
            del self._records[row]
            self.endRemoveRows()

    def _generate_ef_depth_rows(self, first_depth_str: str) -> None:
        """岩芯获取率：根据第一行深度自动生成后续所有行。"""
        if not self.borehole_depth:
            return
        try:
            first_depth = float(first_depth_str)
        except ValueError:
            return
        # 计算需要生成的行数
        depths = []
        current = first_depth
        while current < self.borehole_depth:
            current += SAMPLE_DEPTH_INTERVAL
            if current > self.borehole_depth:
                current = self.borehole_depth
            depths.append(current)
            if current >= self.borehole_depth:
                break
        if not depths:
            return
        # 删除除第一行外的所有行
        while len(self._records) > 1:
            self.beginRemoveRows(QModelIndex(), 1, 1)
            del self._records[1]
            self.endRemoveRows()
        # 添加新行并触发深度同步
        for depth in depths:
            row = len(self._records)
            self.beginInsertRows(QModelIndex(), row, row)
            formatted = format_numeric_value(f"{depth:.1f}")
            self._records.append(TestRecord(values=[formatted]))
            self.endInsertRows()
            if self.on_depth_changed:
                self.on_depth_changed(row, formatted)


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
        self.setMinimumHeight(340)
        self._suffix = suffix
        self._begin_change = begin_change
        self._end_change = end_change
        self._borehole: Borehole | None = None
        self._edit_token: Any = None
        self._model = TestRecordModel(suffix, self)
        self._model.before_set_data = self._on_before_edit
        self._model.after_set_data = self._on_after_edit
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
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.setMinimumHeight(280)
        self._delegate = _TrackingDelegate(self._table)
        self._table.setItemDelegate(self._delegate)
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
            with self._model.suppress_callbacks():
                self._auto_fill_sample_id(row)
        self._table.setCurrentIndex(self._model.index(row, 0))

    def _auto_fill_sample_id(self, row: int) -> None:
        if self._suffix != "o" or not self._borehole:
            return
        prefix = self._borehole.prefix
        max_num = 0
        for record in self._model.records:
            if len(record.values) > 2 and record.values[2]:
                try:
                    num = int(record.values[2].split("-")[-1])
                    max_num = max(max_num, num)
                except (ValueError, IndexError):
                    pass
        sample_id = f"{prefix}-{max_num + 1}"
        idx = self._model.index(row, 2)
        self._model.setData(idx, sample_id)

    def _delete(self) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes or not self._borehole:
            return
        row = indexes[0].row()
        with self._change(f"删除试验数据 .-{self._suffix} 第{row + 1}行"):
            self._model.remove_record(row)

    def _show_context_menu(self, pos: QPoint) -> None:
        index = self._table.indexAt(pos)
        menu = QMenu(self)
        if index.isValid():
            row = index.row()
            menu.addAction("在上方添加行", lambda: self._insert_and_select(row))
            menu.addAction("在下方添加行", lambda: self._insert_and_select(row + 1))
            menu.addSeparator()
            menu.addAction("删除行", lambda: self._delete_row(row))
        else:
            menu.addAction("添加行", self._add)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _insert_and_select(self, row: int) -> None:
        if not self._borehole:
            return
        with self._change(f"在上方添加试验数据 .-{self._suffix} 行"):
            inserted = self._model.insert_at(row)
            self._auto_fill_sample_id(inserted)
        self._table.setCurrentIndex(self._model.index(inserted, 0))

    def _delete_row(self, row: int) -> None:
        if not self._borehole:
            return
        with self._change(f"删除试验数据 .-{self._suffix} 第{row + 1}行"):
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
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
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

    def load_borehole(self, borehole: Borehole | None) -> None:
        self._borehole = borehole
        for section in self._sections.values():
            section.commit_active_edit()
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
            row = index // 2
            col = index % 2
            self._grid_layout.addWidget(section, row, col)
            self._sections[suffix] = section

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
