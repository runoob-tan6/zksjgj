from pathlib import Path

import borehole.ui.main_window as main_window_module
from borehole.application.project_service import create_empty_project, load_project
from borehole.application.save_service import SaveService
from borehole.domain.models import Borehole
from borehole.ui.main_window import MainWindow


def _write_project(folder: Path) -> None:
    main_lines = [
        "ZK1",
        "12.5",
        "101.25",
        "测试地点",
        ",90",
        "100",
        "2026.1.1",
        "测试项目",
        "001",
        "详勘",
        "0,0",
        "2026.1.2",
        "12.5",
        "L",
        ",90",
        "测试单位",
        "★",
    ]
    (folder / "ZK1").write_text("\n".join(main_lines), encoding="utf-8")
    (folder / "ZK1.-c").write_text("5.0,11\n12.5,22\n★", encoding="utf-8")


def _window(qtbot, monkeypatch, folder: Path) -> tuple[MainWindow, Borehole]:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "_project", create_empty_project()))
    project = load_project(folder)
    borehole = project.boreholes["ZK1"]
    window._project = project
    window._refresh_borehole_list()
    window._load_current_borehole(borehole)
    window._select_in_tree("ZK1")
    return window, borehole


def _edit_deepest_depth(window: MainWindow) -> None:
    model = window._main_file_page._basic_data_page._model
    assert model.setData(model.index(1, 1), "14")


def test_synced_hole_depth_is_saved_and_survives_reload(qtbot, monkeypatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    window, borehole = _window(qtbot, monkeypatch, tmp_path)

    _edit_deepest_depth(window)

    assert borehole.main.depth == "14.0"
    assert {"c", "main"} <= borehole.dirty_suffixes
    SaveService(window._project).save()
    reloaded = load_project(tmp_path).boreholes["ZK1"]
    assert reloaded.main.depth == "14.0"
    assert reloaded.layers[-1].bottom_depth == "14.0"


def test_synced_hole_depth_is_included_in_undo_and_redo(qtbot, monkeypatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    window, borehole = _window(qtbot, monkeypatch, tmp_path)
    _edit_deepest_depth(window)

    window._undo()

    assert borehole.main.depth == "12.5"
    assert borehole.layers[-1].bottom_depth == "12.5"

    window._redo()

    assert borehole.main.depth == "14.0"
    assert borehole.layers[-1].bottom_depth == "14.0"
    assert "main" in borehole.dirty_suffixes
