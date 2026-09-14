"""应用入口。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .infrastructure.logging_setup import install_exception_hook, setup_logging
from .ui.main_window import MainWindow


def _qt_message_handler(message_type: QtMsgType, _context: QMessageLogContext, message: str) -> None:
    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }
    logging.getLogger("borehole.qt").log(levels.get(message_type, logging.INFO), message)


def _get_icon_path() -> Path | None:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        bundled = base / "assets" / "app_icon.ico"
        if bundled.exists():
            return bundled
        internal = Path(getattr(sys, "_MEIPASS")) / "assets" / "app_icon.ico"
        if internal.exists():
            return internal
        return None
    dev_path = Path(__file__).resolve().parents[3] / "assets" / "app_icon.ico"
    return dev_path if dev_path.exists() else None


def main() -> None:
    log_path = setup_logging()
    install_exception_hook()
    qInstallMessageHandler(_qt_message_handler)
    logging.getLogger(__name__).info("Application starting; log=%s", log_path)
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BoreholeEditor.v3")

    app = QApplication(sys.argv)
    app.setApplicationName("钻孔数据编辑工具")
    app.setApplicationVersion("3.1.0")

    icon_path = _get_icon_path()
    if icon_path:
        icon = QIcon(str(icon_path))
        app.setWindowIcon(icon)

    app.setStyleSheet("""
        QWidget {
            font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
            font-size: 10pt;
            background: #F7F8FC;
            color: #20242A;
        }
        QMainWindow {
            background: #F7F8FC;
        }
        QLabel[class="title"] {
            font-size: 15pt;
            font-weight: bold;
            margin-bottom: 8px;
        }
        QTreeView, QTableView {
            background: #FFFFFF;
            border: none;
            alternate-background-color: #F8F9FC;
            selection-background-color: #D6DEFF;
            selection-color: #1A1F2E;
        }
        QTreeView::item, QTableView::item {
            padding: 4px;
            border: none;
        }
        QTreeView::item:selected {
            background: #D6DEFF;
            border-left: 3px solid #6C63FF;
            padding-left: 1px;
            font-weight: bold;
        }
        QTreeView::item:selected:active {
            background: #C7D0FE;
        }
        QHeaderView::section {
            background: #F1F4FA;
            color: #3A4252;
            padding: 8px;
            border: none;
            border-right: 1px solid #E2E5ED;
            border-bottom: 1px solid #E2E5ED;
        }
        QPushButton {
            background: #EEF2FF;
            color: #27315D;
            border: none;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background: #E0E7FF;
        }
        QTabWidget::pane {
            border: none;
            background: #FFFFFF;
        }
        QTabBar::tab {
            background: #EEF2F7;
            color: #586174;
            padding: 8px 18px;
            border: none;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background: #FFFFFF;
            color: #20242A;
        }
        QLineEdit, QTextEdit, QPlainTextEdit {
            background: #FFFFFF;
            border: 1px solid #D1D5DB;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QLineEdit:focus, QTextEdit:focus {
            border-color: #6C63FF;
        }
        QGroupBox {
            border: 1px solid #E2E5ED;
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 16px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }
        QStatusBar {
            background: #F1F4FA;
            color: #586174;
            border-top: 1px solid #E2E5ED;
        }
        QMenuBar {
            background: #F7F8FC;
        }
        QMenuBar::item:selected {
            background: #E0E7FF;
        }
        QMenu {
            background: #FFFFFF;
            border: 1px solid #E2E5ED;
        }
        QMenu::item:selected {
            background: #E0E7FF;
        }
        QSplitter::handle {
            background: #E2E5ED;
            width: 2px;
        }
    """)

    window = MainWindow()
    if icon_path:
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
