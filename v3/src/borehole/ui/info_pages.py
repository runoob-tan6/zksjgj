"""原始文本和校验结果页面。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from ..domain.models import Borehole
from ..domain.validators import validate_borehole


class RawTextPage(QWidget):
    """原始文本只读展示。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        layout.addWidget(self._text)

    def load_borehole(self, borehole: Borehole | None) -> None:
        self._text.clear()
        if not borehole:
            return
        for name, content in borehole.raw_texts.items():
            self._text.append(f"===== {name} =====")
            self._text.append(content)
            self._text.append("")

    def set_content(self, name: str, content: str) -> None:
        self._text.clear()
        self._text.append(f"===== {name} =====")
        self._text.append(content)


class ValidationPage(QWidget):
    """校验结果展示。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        layout.addWidget(self._text)

    def load_borehole(self, borehole: Borehole | None) -> None:
        self._text.clear()
        if not borehole:
            self._text.setPlainText("暂无钻孔数据。")
            return
        messages = validate_borehole(borehole)
        if not messages:
            self._text.setPlainText("当前钻孔未发现明显问题。")
        else:
            self._text.setPlainText("\n".join(f"- {msg}" for msg in messages))


class EditableTextPage(QWidget):
    """可编辑的文本页面，用于编辑额外数据文件。"""

    content_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        self._label = QLabel()
        layout.addWidget(self._label)
        self._text = QTextEdit()
        layout.addWidget(self._text)
        self._name = ""
        self._on_save = None
        self._loading = False
        self._text.textChanged.connect(self._on_text_changed)

    def set_content(self, name: str, content: str, on_save=None) -> None:
        self._loading = True
        self._name = name
        self._on_save = on_save
        self._label.setText(f"===== {name} =====")
        self._text.setPlainText(content)
        self._loading = False

    def _on_text_changed(self) -> None:
        if self._loading or not self._on_save:
            return
        self._on_save(self._name, self._text.toPlainText())
        self.content_changed.emit()
