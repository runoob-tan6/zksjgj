from pathlib import Path

from PySide6.QtWidgets import QApplication

from borehole.domain.enums import HoleType
from borehole.domain.models import Borehole, MainFileData
from borehole.domain.models import TestRecord as Record
from borehole.ui.test_data_page import VISIBLE_TEST_ROWS
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
    finally:
        app.setStyleSheet(original_style_sheet)
