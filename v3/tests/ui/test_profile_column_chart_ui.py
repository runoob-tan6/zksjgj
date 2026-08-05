from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox

import borehole.ui.main_window as main_window_module
from borehole.application.column_chart_service import synchronize_column_charts
from borehole.application.project_service import create_empty_project, create_new_borehole
from borehole.application.undo_manager import BoreholeSnapshot, UndoAction
from borehole.domain.models import ProfileFile, ProjectData
from borehole.ui.main_window import MainWindow


def _window(qtbot, monkeypatch, folder: Path) -> MainWindow:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes)
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "_project", create_empty_project()))
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


def test_borehole_rename_migrates_undo_history_across_undo_and_redo(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch, tmp_path)
    borehole = create_new_borehole(window._project, "ZK1")
    window._load_current_borehole(borehole)
    manager = window._get_undo_manager(borehole)
    assert manager is not None
    before = BoreholeSnapshot.capture(borehole)

    window._on_hole_id_changed("ZK1", "NZK3")
    after = BoreholeSnapshot.capture(borehole)
    manager.push(UndoAction(borehole=borehole, label="重命名钻孔", before=before, after=after))

    assert window._undo_controller.managers == {"NZK3": manager}
    window._undo()
    assert borehole.prefix == "ZK1"
    assert window._undo_controller.managers == {"ZK1": manager}
    window._redo()
    assert borehole.prefix == "NZK3"
    assert window._undo_controller.managers == {"NZK3": manager}

    window._project = create_empty_project()
    window.close()


def _project_with_profile(folder: Path) -> ProjectData:
    profile = ProfileFile(
        name="H8",
        path=folder / "H8",
        content="main",
        extra_files={"d0": "d0", "g": "g", "k": "k"},
    )
    project = ProjectData(folder=folder, profile_files={"H8": profile})
    synchronize_column_charts(project)
    return project


def _top_level_labels(window: MainWindow) -> list[str]:
    return [window._tree.topLevelItem(index).text(0) for index in range(window._tree.topLevelItemCount())]


def test_profile_list_uses_natural_numeric_order(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch, tmp_path)
    names = ("H10", "H2", "H1", "Z10", "Z2", "Z1")
    window._project.profile_files = {
        name: ProfileFile(name=name, path=tmp_path / name) for name in names
    }

    window._refresh_borehole_list()

    profile_node = next(
        window._tree.topLevelItem(index)
        for index in range(window._tree.topLevelItemCount())
        if window._tree.topLevelItem(index).text(0) == "剖面图"
    )
    labels = [profile_node.child(index).text(0) for index in range(profile_node.childCount())]
    assert labels == ["H1", "H2", "H10", "Z1", "Z2", "Z10"]
    window._project = create_empty_project()
    window.close()


def test_tree_uses_profile_and_column_chart_group_labels(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch, tmp_path)
    window._project = _project_with_profile(tmp_path)

    window._refresh_borehole_list()

    labels = _top_level_labels(window)
    assert "剖面图" in labels
    assert "柱状图" in labels
    assert "剖面及柱状图" not in labels
    assert "项目配置文件" not in labels
    window._project = create_empty_project()
    window.close()


def test_profile_context_menu_includes_rename_command(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch, tmp_path)
    window._project = _project_with_profile(tmp_path)
    window._refresh_borehole_list()
    window.show()
    qtbot.waitExposed(window)
    window._select_in_tree("profile:H8")
    item = window._tree.currentItem()
    assert item is not None
    captured: list[str] = []

    class CapturingMenu(QMenu):
        def exec(self, *_args) -> None:
            captured.extend("<separator>" if action.isSeparator() else action.text() for action in self.actions())

    monkeypatch.setattr(main_window_module, "QMenu", CapturingMenu)
    position = window._tree.visualItemRect(item).center()

    window._show_context_menu(position)

    assert captured == ["复制剖面文件", "重命名剖面文件", "<separator>", "删除剖面文件"]
    window._project = create_empty_project()
    window.close()


def test_profile_rename_updates_model_selection_and_keeps_first_old_name(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch, tmp_path)
    window._project = _project_with_profile(tmp_path)
    window._refresh_borehole_list()
    answers = iter([("h9", True), ("H10", True)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: next(answers))

    window._rename_profile("H8")
    window._rename_profile("H9")

    profile = window._project.profile_files["H10"]
    assert profile.name == "H10"
    assert profile.path == tmp_path / "H10"
    assert profile.old_name == "H8"
    assert profile.modified
    selected = window._tree.currentItem()
    assert selected is not None
    assert selected.data(0, Qt.ItemDataRole.UserRole) == "profile:H10"
    window._project = create_empty_project()
    window.close()


def test_profile_rename_same_name_is_noop(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch, tmp_path)
    window._project = _project_with_profile(tmp_path)
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: (" h8 ", True))

    window._rename_profile("H8")

    assert set(window._project.profile_files) == {"H8"}
    assert window._project.profile_files["H8"].old_name is None


def test_profile_rename_rejects_invalid_name(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch, tmp_path)
    window._project = _project_with_profile(tmp_path)
    warnings: list[str] = []
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: ("bad-name", True))
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message, *_args, **_kwargs: warnings.append(message),
    )

    window._rename_profile("H8")

    assert set(window._project.profile_files) == {"H8"}
    assert warnings == ["文件名格式不正确，应为 H1、Z2 等格式。"]


def test_profile_rename_rejects_model_and_disk_conflicts(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch, tmp_path)
    window._project = _project_with_profile(tmp_path)
    window._project.profile_files["H9"] = ProfileFile(name="H9", path=tmp_path / "H9")
    warnings: list[str] = []
    answers = iter([("H9", True), ("H10", True)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: next(answers))
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message, *_args, **_kwargs: warnings.append(message),
    )
    (tmp_path / "H10.-d0").write_text("conflict", encoding="utf-8")

    window._rename_profile("H8")
    window._rename_profile("H8")

    assert set(window._project.profile_files) == {"H8", "H9"}
    assert window._project.profile_files["H8"].old_name is None
    assert len(warnings) == 2
    window._project = create_empty_project()
    window.close()
