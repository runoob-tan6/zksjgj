from types import SimpleNamespace

import borehole.ui.main_window as main_window_module
from borehole.application.project_service import create_empty_project
from borehole.ui.main_window import MainWindow


def test_sync_save_delegates_to_save_service(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    calls: list[str] = []

    class FakeSaveService:
        def __init__(self, _project) -> None:
            pass

        def summary(self):
            return SimpleNamespace(has_changes=True)

        def save(self):
            calls.append("save")
            return SimpleNamespace(as_tuple=lambda: ([], 0))

    monkeypatch.setattr(main_window_module, "SaveService", FakeSaveService, raising=False)
    window = MainWindow()
    qtbot.addWidget(window)
    window._project = create_empty_project()

    assert window._save_data_sync()
    assert calls == ["save"]

    window.close()
