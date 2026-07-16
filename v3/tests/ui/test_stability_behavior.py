from pathlib import Path

from PySide6.QtWidgets import QMessageBox

import borehole.ui.main_window as main_window_module
from borehole.domain.enums import HoleType
from borehole.domain.models import Borehole, MainFileData, ProfileFile, ProjectData
from borehole.ui.main_window import MainWindow


def _window(qtbot, monkeypatch) -> MainWindow:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window)
    return window


def test_summary_ignores_non_finite_depths(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch)
    finite = Borehole("ZK1", tmp_path, HoleType.ZK, main=MainFileData(["ZK1", "10"]))
    invalid = Borehole("ZK2", tmp_path, HoleType.ZK, main=MainFileData(["ZK2", "nan"]))
    window._project = ProjectData(folder=tmp_path, boreholes={"ZK1": finite, "ZK2": invalid})

    window._update_summary()

    assert window._summary_label.text().startswith("总深度：10 m")
    window.close()


def test_pending_profile_deletion_is_unsaved_change(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch)
    profile = ProfileFile("H1", tmp_path / "H1")
    window._project = ProjectData(folder=tmp_path, deleted_profiles={"H1": profile})
    prompts: list[str] = []

    def cancel(_parent, _title, text, *_args):
        prompts.append(text)
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "question", cancel)

    assert not window._check_unsaved_changes()
    assert prompts == ['存在未保存的数据修改，是否先保存？\n\n点击"是"保存后继续，点击"否"放弃修改。']

    window._project = ProjectData()
    window.close()
