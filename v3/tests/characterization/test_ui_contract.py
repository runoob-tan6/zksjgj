from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QSplitter, QTabWidget, QTreeWidget

import borehole.ui.main_window as main_window_module
from borehole.ui.main_window import MainWindow


@pytest.fixture
def window(qtbot, monkeypatch) -> Iterator[MainWindow]:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    widget = MainWindow()
    qtbot.addWidget(widget)
    yield widget
    widget.close()


def _menu_contract(window: QMainWindow) -> list[tuple[str, list[tuple[str, str]]]]:
    contract: list[tuple[str, list[tuple[str, str]]]] = []
    for menu_action in window.menuBar().actions():
        menu = menu_action.menu()
        assert menu is not None
        actions = [
            ("<separator>", "") if action.isSeparator() else (action.text(), action.shortcut().toString())
            for action in menu.actions()
        ]
        contract.append((menu_action.text(), actions))
    return contract


def test_main_window_preserves_v2_navigation(window: MainWindow) -> None:
    assert window.windowTitle() == "钻孔数据编辑工具 v3.1"
    assert (window.minimumWidth(), window.minimumHeight()) == (980, 640)
    assert (window.width(), window.height()) == (1180, 760)
    assert window.acceptDrops()

    assert _menu_contract(window) == [
        (
            "文件(&F)",
            [
                ("选择项目...", "Ctrl+O"),
                ("重新加载", "Ctrl+R"),
                ("打开文件夹", ""),
                ("<separator>", ""),
                ("退出", "Ctrl+Q"),
            ],
        ),
        ("编辑(&E)", [("撤销", "Ctrl+Z"), ("恢复", "Ctrl+Y")]),
        (
            "工具(&T)",
            [
                ("新增钻孔", ""),
                ("新增剖面文件", ""),
                ("校验项目", ""),
                ("导出试验汇总...", ""),
                ("<separator>", ""),
                ("保存数据", "Ctrl+S"),
            ],
        ),
    ]


def test_main_window_preserves_v2_widget_structure(window: MainWindow) -> None:
    splitter = window.centralWidget().findChild(QSplitter)
    assert splitter is not None
    assert splitter.orientation() == Qt.Orientation.Horizontal
    assert splitter.count() == 2
    assert isinstance(splitter.widget(1), QTabWidget)

    tree = splitter.widget(0).findChild(QTreeWidget)
    assert tree is window._tree
    assert tree.isHeaderHidden()
    assert tree.indentation() == 16
    assert tree.alternatingRowColors()

    assert [window._tabs.tabText(index) for index in range(window._tabs.count())] == [
        "基本信息",
        "试验数据",
        "标贯分析",
        "数据文件",
        "原始文本",
        "校验结果",
    ]
    assert window._status_label.text() == "未加载项目。请选择项目文件夹。"
    assert window._summary_label.text() == "总深度：-- m | 取样：0 | 标贯：0 | 注水：0 | 压水：0"
