from pathlib import Path

from PySide6.QtWidgets import QInputDialog, QMessageBox

import borehole.ui.main_window as main_window_module
from borehole.application.project_service import create_empty_project
from borehole.domain.models import ProjectData
from borehole.ui.main_window import MainWindow


def _window(qtbot, monkeypatch, folder: Path) -> MainWindow:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window)
    window._project = ProjectData(folder=folder)
    return window


def test_borehole_add_copy_delete_and_rename_resynchronize_charts(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch, tmp_path)
    answers = iter([("ZK1", True), ("ZK2", True)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: next(answers))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes)

    window._add_borehole()
    assert window._project.project_files["0yzk"].extra_files["zkt"] == "ZK1\n★"
    assert window._project.project_files["0nzk"].extra_files["zkt"] == "★"

    window._copy_borehole()
    assert window._project.project_files["0yzk"].extra_files["zkt"] == "ZK1\nZK2\n★"

    window._delete_borehole()
    assert window._project.project_files["0yzk"].extra_files["zkt"] == "ZK1\n★"

    window._on_hole_id_changed("ZK1", "NZK3")
    assert window._project.project_files["0yzk"].extra_files["zkt"] == "★"
    assert window._project.project_files["0nzk"].extra_files["zkt"] == "NZK3\n★"

    window._project = create_empty_project()
    window.close()
