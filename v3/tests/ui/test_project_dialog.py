from pathlib import Path

from PySide6.QtWidgets import QFileDialog

import borehole.ui.main_window as main_window_module
from borehole.domain.models import ProjectData
from borehole.ui.main_window import MainWindow


def test_choose_project_starts_in_current_project_folder(qtbot, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window)
    current_project = tmp_path / "当前项目"
    current_project.mkdir()
    window._project = ProjectData(folder=current_project)
    captured: dict[str, str] = {}

    def choose_directory(_parent, _title, directory):
        captured["directory"] = directory
        return ""

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose_directory)

    window._choose_project()

    assert captured["directory"] == str(current_project)
