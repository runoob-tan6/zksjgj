"""基础数据编辑页面 - QTableView + 自定义 Model。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..domain.models import BasicLayer, Borehole
from .format_utils import format_numeric_value

COLUMNS = ["层号", "层底深度 .-c", "岩性代号 .-c", "地层时代 .-b", "钻孔结构 .-d", "风化 .-g", "岩性描述 .-h"]
ATTR_MAP = ["", "bottom_depth", "lithology_code", "formation", "structure", "weathering", "description"]


class BasicLayerModel(QAbstractTableModel):
    """基础地层数据模型。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layers: list[BasicLayer] = []
        self._loading = False
        self.before_set_data: Callable[[], None] | None = None
        self.after_set_data: Callable[[], None] | None = None
        self.on_description_changed: Callable[[str, str, str, str], None] | None = None

    def load(self, layers: list[BasicLayer]) -> None:
        self._loading = True
        self.beginResetModel()
        self._layers = layers
        self.endResetModel()
        self._loading = False

    def rowCount(self, _parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(self._layers)

    def columnCount(self, _parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return COLUMNS[section]
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
        layer = self._layers[index.row()]
        col = index.column()
        if col == 0:
            return str(index.row() + 1)
        attr = ATTR_MAP[col]
        return getattr(layer, attr, "")

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        if index.column() == 0:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def setData(
        self, index: QModelIndex | QPersistentModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        layer = self._layers[index.row()]
        attr = ATTR_MAP[index.column()]
        if not attr:
            return False
        formatted = format_numeric_value(str(value)) if index.column() == 1 else str(value)
        old_value = getattr(layer, attr)
        if str(old_value) == formatted:
            return False
        if not self._loading and self.before_set_data:
            self.before_set_data()
        setattr(layer, attr, formatted)
        self.dataChanged.emit(index, index)
        # 岩性描述同步：修改了 description 列时通知
        if index.column() == 6 and not self._loading and self.on_description_changed:
            self.on_description_changed(formatted, layer.lithology_code, layer.formation, layer.weathering)
        if not self._loading and self.after_set_data:
            self.after_set_data()
        return True

    def get_layer(self, row: int) -> BasicLayer | None:
        if 0 <= row < len(self._layers):
            return self._layers[row]
        return None

    def insert_row(self, position: int) -> int:
        clamped = max(0, min(position, len(self._layers)))
        self.beginInsertRows(QModelIndex(), clamped, clamped)
        self._layers.insert(clamped, BasicLayer())
        self.endInsertRows()
        return clamped

    def remove_row(self, position: int) -> None:
        if 0 <= position < len(self._layers):
            self.beginRemoveRows(QModelIndex(), position, position)
            del self._layers[position]
            self.endRemoveRows()


class BasicDataPage(QWidget):
    """基础数据编辑页。"""

    layer_changed = Signal(str)
    description_changed = Signal(str, str, str, str)  # (description, lithology_code, formation, weathering)

    def __init__(
        self,
        begin_change: Callable | None = None,
        end_change: Callable | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._borehole: Borehole | None = None
        self._model = BasicLayerModel(self)
        self._begin_change = begin_change
        self._end_change = end_change
        self._model.before_set_data = self._on_before_edit
        self._model.after_set_data = self._on_after_edit
        self._model.on_description_changed = self._emit_description_changed
        self._edit_token = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QHBoxLayout()
        title = QLabel("基础数据")
        title.setProperty("class", "title")
        header.addWidget(title)
        header.addStretch()

        btn_add = QPushButton("添加行")
        btn_add.clicked.connect(self._add_layer)
        header.addWidget(btn_add)

        btn_delete = QPushButton("删除行")
        btn_delete.clicked.connect(self._delete_layer)
        header.addWidget(btn_delete)

        layout.addLayout(header)

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table)

    def load_borehole(self, borehole: Borehole | None) -> None:
        self._borehole = borehole
        self._edit_token = None
        if borehole:
            self._model.load(borehole.layers)
        else:
            self._model.load([])

    def _on_before_edit(self) -> None:
        if not self._borehole or not self._begin_change:
            return
        if self._edit_token is None:
            self._edit_token = self._begin_change(self._borehole, "修改基础数据")

    def _on_after_edit(self) -> None:
        if self._edit_token and self._end_change:
            self._end_change(self._edit_token)
            self._edit_token = None
        self._mark_all_dirty()

    def _emit_description_changed(self, desc: str, litho: str, form: str, weathering: str) -> None:
        if desc and litho:
            self.description_changed.emit(desc, litho, form, weathering)

    def _add_layer(self) -> None:
        if not self._borehole:
            return
        token = self._begin_change(self._borehole, "添加基础数据行") if self._begin_change else None
        row = self._model.rowCount()
        self._model.insert_row(row)
        self._mark_all_dirty()
        if self._end_change:
            self._end_change(token)

    def _delete_layer(self) -> None:
        if not self._borehole:
            return
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return
        row = indexes[0].row()
        token = self._begin_change(self._borehole, f"删除基础数据第{row + 1}行") if self._begin_change else None
        self._model.remove_row(row)
        self._mark_all_dirty()
        if self._end_change:
            self._end_change(token)

    def _mark_all_dirty(self) -> None:
        for suffix in ("c", "b", "d", "g", "h"):
            self.layer_changed.emit(suffix)

    def _show_context_menu(self, pos: QPoint) -> None:
        index = self._table.indexAt(pos)
        menu = QMenu(self)
        if index.isValid():
            row = index.row()
            menu.addAction("在上方添加行", lambda: self._insert_at(row))
            menu.addAction("在下方添加行", lambda: self._insert_at(row + 1))
            menu.addSeparator()
            menu.addAction("删除行", lambda: self._delete_row(row))
        else:
            menu.addAction("添加行", self._add_layer)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _insert_at(self, position: int) -> None:
        if not self._borehole:
            return
        token = self._begin_change(self._borehole, f"在第{position + 1}行上方插入") if self._begin_change else None
        self._model.insert_row(position)
        self._mark_all_dirty()
        if self._end_change:
            self._end_change(token)

    def _delete_row(self, row: int) -> None:
        if not self._borehole:
            return
        token = self._begin_change(self._borehole, f"删除基础数据第{row + 1}行") if self._begin_change else None
        self._model.remove_row(row)
        self._mark_all_dirty()
        if self._end_change:
            self._end_change(token)
