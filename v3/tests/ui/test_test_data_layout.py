from pathlib import Path

from PySide6.QtWidgets import QApplication

from borehole.domain.enums import HoleType
from borehole.domain.models import Borehole, MainFileData
from borehole.domain.models import TestRecord as Record
from borehole.ui.test_data_page import MIN_CORE_SECTION_HEIGHT, VISIBLE_TEST_ROWS
from borehole.ui.test_data_page import TestDataPage as DataPage
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
