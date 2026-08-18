from pathlib import Path

from PySide6.QtWidgets import QApplication, QLineEdit

from borehole.domain.enums import HoleType
from borehole.domain.models import BasicLayer, Borehole
from borehole.ui.basic_data_page import BasicDataPage


def test_description_editor_keeps_full_glyph_height(qtbot) -> None:
    app = QApplication.instance()
    assert app is not None
    original_style_sheet = app.styleSheet()
    app.setStyleSheet(
        "QTableView::item { padding: 4px; } "
        "QLineEdit { border: 1px solid #D1D5DB; padding: 4px 8px; }"
    )
    try:
        page = BasicDataPage()
        qtbot.addWidget(page)
        page.resize(1180, 760)
        page.load_borehole(
            Borehole(
                prefix="ZK1",
                folder=Path("."),
                hole_type=HoleType.ZK,
                layers=[BasicLayer(description="王，。")],
            )
        )
        page.show()
        description_index = page._table.model().index(0, 6)
        page._table.edit(description_index)
        qtbot.waitUntil(lambda: page._table.findChild(QLineEdit) is not None)
        editor = page._table.findChild(QLineEdit)

        assert editor is not None
        assert editor.height() >= editor.minimumSizeHint().height()
    finally:
        app.setStyleSheet(original_style_sheet)
