"""主文件编辑页面 + 基础数据（合并为一个 Tab）。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ..domain.models import EDITABLE_MAIN_INDICES, MAIN_FIELD_NAMES, Borehole
from .basic_data_page import BasicDataPage
from .format_utils import format_numeric_value


class MainFilePage(QWidget):
    """主文件 + 基础数据合并页。"""

    field_changed = Signal(int, str, str)
    hole_id_changed = Signal(str, str)
    layer_changed = Signal(str)
    description_changed = Signal(str, str, str, str, str)

    def __init__(
        self,
        begin_change: Callable | None = None,
        end_change: Callable | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._borehole: Borehole | None = None
        self._loading = False
        self._entries: dict[int, QLineEdit] = {}
        self._begin_change = begin_change
        self._end_change = end_change
        self._edit_token = None
        self._edit_index: int | None = None
        self._edit_original_value = ""
        self._basic_data_page = BasicDataPage(begin_change, end_change)
        self._basic_data_page.layer_changed.connect(self.layer_changed)
        self._basic_data_page.layer_changed.connect(self._sync_depth_from_layers)
        self._basic_data_page.description_changed.connect(self.description_changed)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("主文件")
        title.setProperty("class", "title")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        for position, index in enumerate(EDITABLE_MAIN_INDICES):
            row = position // 2
            col = (position % 2) * 2
            label_text = MAIN_FIELD_NAMES[index]
            if label_text.endswith(":"):
                label_text = label_text[:-1]
            label = QLabel(label_text + "：")
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(label, row, col)

            entry = QLineEdit()
            entry.editingFinished.connect(lambda idx=index: self._on_edit_finished(idx))
            entry.installEventFilter(self)
            self._entries[index] = entry
            grid.addWidget(entry, row, col + 1)

        layout.addLayout(grid)

        layout.addSpacing(12)
        layout.addWidget(self._basic_data_page, 1)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if isinstance(obj, QLineEdit) and event.type() == QEvent.Type.FocusIn:
            for idx, entry in self._entries.items():
                if entry is obj:
                    self._begin_field_edit(idx)
                    break
        return super().eventFilter(obj, event)

    def _begin_field_edit(self, index: int) -> None:
        if self._loading or not self._borehole:
            return
        if self._edit_token is not None and self._edit_index != index:
            self._commit_field_edit()
        self._edit_index = index
        self._edit_original_value = self._entries[index].text()
        self._edit_token = (
            self._begin_change(self._borehole, f"修改主文件：{MAIN_FIELD_NAMES[index]}")
            if self._begin_change
            else None
        )

    def _commit_field_edit(self) -> None:
        if self._edit_token is None or self._edit_index is None:
            return
        token = self._edit_token
        self._edit_token = None
        self._edit_index = None
        if self._end_change:
            self._end_change(token)

    def load_borehole(self, borehole: Borehole | None) -> None:
        self._loading = True
        self._borehole = borehole
        self._edit_token = None
        self._edit_index = None
        if not borehole:
            for entry in self._entries.values():
                entry.clear()
            self._loading = False
            self._basic_data_page.load_borehole(None)
            return
        lines = borehole.main.normalized_lines()
        for index, entry in self._entries.items():
            entry.setText(lines[index])
        self._basic_data_page.load_borehole(borehole)
        self._loading = False

    def _on_edit_finished(self, index: int) -> None:
        if self._loading or not self._borehole:
            return
        entry = self._entries[index]
        new_value = entry.text().strip()
        if index in (1, 2):
            new_value = format_numeric_value(new_value)
            entry.setText(new_value)
        lines = self._borehole.main.normalized_lines()
        old_value = lines[index]
        if new_value == old_value:
            self._edit_token = None
            self._edit_index = None
            return

        if index == 0:
            old_prefix = self._borehole.prefix
            self._borehole.main.lines[0] = new_value
            self._commit_field_edit()
            self.hole_id_changed.emit(old_prefix, new_value)
        else:
            self._borehole.main.lines[index] = new_value
            if index == 1:
                self._borehole.main.lines[12] = new_value
            self._commit_field_edit()
            self.field_changed.emit(index, old_value, new_value)

    def set_hole_id(self, value: str) -> None:
        self._loading = True
        if 0 in self._entries:
            self._entries[0].setText(value)
        if self._borehole:
            lines = self._borehole.main.normalized_lines()
            lines[0] = value
            self._borehole.main.lines = lines
        self._loading = False

    def _sync_depth_from_layers(self) -> None:
        if self._loading or not self._borehole:
            return
        layers = self._borehole.layers
        if not layers:
            return
        max_depth = ""
        for layer in layers:
            d = layer.bottom_depth.strip()
            if not d:
                continue
            try:
                val = float(d)
                if not max_depth or val > float(max_depth):
                    max_depth = d
            except ValueError:
                continue
        if not max_depth:
            return
        formatted = format_numeric_value(max_depth)
        lines = self._borehole.main.normalized_lines()
        if lines[1] == formatted:
            return
        old_depth = lines[1]
        self._loading = True
        self._borehole.main.lines[1] = formatted
        self._borehole.main.lines[12] = formatted
        if 1 in self._entries:
            self._entries[1].setText(formatted)
        self._loading = False
        self.field_changed.emit(1, old_depth, formatted)
