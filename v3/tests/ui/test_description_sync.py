from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

import borehole.ui.main_window as main_window_module
from borehole.application.project_service import create_empty_project
from borehole.application.undo_manager import CompositeUndoAction
from borehole.domain.enums import HoleType
from borehole.domain.models import BasicLayer, Borehole, ProjectData
from borehole.ui.main_window import MainWindow


def _window(qtbot, monkeypatch) -> MainWindow:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "_project", create_empty_project()))
    return window


def _borehole(folder: Path, prefix: str, layer: BasicLayer) -> Borehole:
    return Borehole(prefix=prefix, folder=folder, hole_type=HoleType.ZK, layers=[layer])


def _load_boreholes(window: MainWindow, folder: Path, source: Borehole, targets: list[Borehole]) -> None:
    boreholes = {borehole.prefix: borehole for borehole in [source, *targets]}
    window._project = ProjectData(folder=folder, boreholes=boreholes)
    window._refresh_borehole_list()
    window._load_current_borehole(source)
    window._select_in_tree(source.prefix)


def _edit_source_description(window: MainWindow, description: str) -> None:
    model = window._main_file_page._basic_data_page._model
    index = model.index(0, 6)
    assert model.setData(index, description)


def test_sync_requires_exact_formation_and_preserves_existing_descriptions(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    window = _window(qtbot, monkeypatch)
    source = _borehole(
        tmp_path,
        "ZK1",
        BasicLayer(lithology_code="3-2", formation="", weathering="强风化"),
    )
    blank_target = _borehole(
        tmp_path,
        "ZK2",
        BasicLayer(lithology_code="3-2", formation="", weathering="强风化"),
    )
    q4_target = _borehole(
        tmp_path,
        "ZK3",
        BasicLayer(lithology_code="3-2", formation="Q4", weathering="强风化"),
    )
    filled_target = _borehole(
        tmp_path,
        "ZK4",
        BasicLayer(
            lithology_code="3-2",
            formation="",
            weathering="强风化",
            description="已有描述",
        ),
    )
    _load_boreholes(window, tmp_path, source, [blank_target, q4_target, filled_target])

    window._sync_description("", "同步文本", "3-2", "", "强风化")

    assert blank_target.layers[0].description == "同步文本"
    assert q4_target.layers[0].description == ""
    assert filled_target.layers[0].description == "已有描述"
    assert blank_target.dirty_suffixes == {"h"}
    assert q4_target.dirty_suffixes == set()
    assert filled_target.dirty_suffixes == set()


def test_table_edit_keeps_sync_status_and_records_sync_last(qtbot, monkeypatch, tmp_path: Path) -> None:
    window = _window(qtbot, monkeypatch)
    source = _borehole(
        tmp_path,
        "ZK1",
        BasicLayer(lithology_code="3-2", formation="Q4", weathering="强风化"),
    )
    target = _borehole(
        tmp_path,
        "ZK2",
        BasicLayer(lithology_code="3-2", formation="Q4", weathering="强风化"),
    )
    _load_boreholes(window, tmp_path, source, [target])

    _edit_source_description(window, "同步文本")

    manager = window._get_undo_manager(source)
    assert manager is not None
    assert window._status_label.text() == "已同步岩性描述到 1 个钻孔。"
    assert len(manager.undo_stack) == 2
    assert isinstance(manager.undo_stack[-1], CompositeUndoAction)


@pytest.mark.parametrize("target_count", [1, 2])
def test_sync_undo_redo_keeps_source_active(
    qtbot, monkeypatch, tmp_path: Path, target_count: int
) -> None:
    window = _window(qtbot, monkeypatch)
    source = _borehole(
        tmp_path,
        "ZK1",
        BasicLayer(lithology_code="3-2", formation="Q4", weathering="强风化"),
    )
    targets = [
        _borehole(
            tmp_path,
            f"ZK{index + 2}",
            BasicLayer(lithology_code="3-2", formation="Q4", weathering="强风化"),
        )
        for index in range(target_count)
    ]
    _load_boreholes(window, tmp_path, source, targets)
    _edit_source_description(window, "同步文本")
    assert all(target.layers[0].description == "同步文本" for target in targets)

    window._undo()

    assert source.layers[0].description == "同步文本"
    assert all(target.layers[0].description == "" for target in targets)
    assert window._current_borehole is source
    assert window._redo_action.isEnabled()

    window._redo()

    assert source.layers[0].description == "同步文本"
    assert all(target.layers[0].description == "同步文本" for target in targets)
    assert window._current_borehole is source


def test_edit_confirmed_syncs_blank_and_matching_old_descriptions(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    window = _window(qtbot, monkeypatch)
    source = _borehole(
        tmp_path,
        "ZK1",
        BasicLayer(
            lithology_code="3-2",
            formation="Q4",
            weathering="强风化",
            description="原描述",
        ),
    )
    blank_target = _borehole(
        tmp_path,
        "ZK2",
        BasicLayer(lithology_code="3-2", formation="Q4", weathering="强风化"),
    )
    same_target = _borehole(
        tmp_path,
        "ZK3",
        BasicLayer(
            lithology_code="3-2",
            formation="Q4",
            weathering="强风化",
            description="原描述",
        ),
    )
    different_target = _borehole(
        tmp_path,
        "ZK4",
        BasicLayer(
            lithology_code="3-2",
            formation="Q4",
            weathering="强风化",
            description="不同描述",
        ),
    )
    _load_boreholes(window, tmp_path, source, [blank_target, same_target, different_target])
    prompts: list[str] = []

    def confirm(_parent, title, message, *_args, **_kwargs):
        assert title == "同步岩性描述"
        prompts.append(message)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", confirm)

    _edit_source_description(window, "新描述")

    assert blank_target.layers[0].description == "新描述"
    assert same_target.layers[0].description == "新描述"
    assert different_target.layers[0].description == "不同描述"
    assert prompts == ["发现 1 处其他钻孔的相同地层描述仍为修改前内容。\n\n是否全部同步为新描述？"]
    assert window._status_label.text() == "已同步岩性描述到 2 个钻孔。"


def test_edit_declined_keeps_matching_old_description_but_fills_blank(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    window = _window(qtbot, monkeypatch)
    source = _borehole(
        tmp_path,
        "ZK1",
        BasicLayer(
            lithology_code="3-2",
            formation="Q4",
            weathering="强风化",
            description="原描述",
        ),
    )
    blank_target = _borehole(
        tmp_path,
        "ZK2",
        BasicLayer(lithology_code="3-2", formation="Q4", weathering="强风化"),
    )
    same_target = _borehole(
        tmp_path,
        "ZK3",
        BasicLayer(
            lithology_code="3-2",
            formation="Q4",
            weathering="强风化",
            description="原描述",
        ),
    )
    _load_boreholes(window, tmp_path, source, [blank_target, same_target])
    prompts: list[str] = []

    def decline(_parent, _title, message, *_args, **_kwargs):
        prompts.append(message)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", decline)

    _edit_source_description(window, "新描述")

    assert blank_target.layers[0].description == "新描述"
    assert same_target.layers[0].description == "原描述"
    assert same_target.dirty_suffixes == set()
    assert prompts == ["发现 1 处其他钻孔的相同地层描述仍为修改前内容。\n\n是否全部同步为新描述？"]
    assert window._status_label.text() == "已同步岩性描述到 1 个钻孔。"


def test_edit_without_matching_old_description_does_not_prompt(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    window = _window(qtbot, monkeypatch)
    source = _borehole(
        tmp_path,
        "ZK1",
        BasicLayer(
            lithology_code="3-2",
            formation="Q4",
            weathering="强风化",
            description="原描述",
        ),
    )
    blank_target = _borehole(
        tmp_path,
        "ZK2",
        BasicLayer(lithology_code="3-2", formation="Q4", weathering="强风化"),
    )
    different_target = _borehole(
        tmp_path,
        "ZK3",
        BasicLayer(
            lithology_code="3-2",
            formation="Q4",
            weathering="强风化",
            description="不同描述",
        ),
    )
    _load_boreholes(window, tmp_path, source, [blank_target, different_target])

    def unexpected_prompt(*_args, **_kwargs):
        raise AssertionError("不存在相同旧描述时不应弹出确认框")

    monkeypatch.setattr(QMessageBox, "question", unexpected_prompt)

    _edit_source_description(window, "新描述")

    assert blank_target.layers[0].description == "新描述"
    assert different_target.layers[0].description == "不同描述"


def test_confirmed_matching_description_sync_undoes_and_redoes_as_one_action(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    window = _window(qtbot, monkeypatch)
    source = _borehole(
        tmp_path,
        "ZK1",
        BasicLayer(
            lithology_code="3-2",
            formation="Q4",
            weathering="强风化",
            description="原描述",
        ),
    )
    blank_target = _borehole(
        tmp_path,
        "ZK2",
        BasicLayer(lithology_code="3-2", formation="Q4", weathering="强风化"),
    )
    same_target = _borehole(
        tmp_path,
        "ZK3",
        BasicLayer(
            lithology_code="3-2",
            formation="Q4",
            weathering="强风化",
            description="原描述",
        ),
    )
    _load_boreholes(window, tmp_path, source, [blank_target, same_target])
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    _edit_source_description(window, "新描述")

    window._undo()

    assert source.layers[0].description == "新描述"
    assert blank_target.layers[0].description == ""
    assert same_target.layers[0].description == "原描述"
    assert window._current_borehole is source
    assert window._redo_action.isEnabled()

    window._redo()

    assert blank_target.layers[0].description == "新描述"
    assert same_target.layers[0].description == "新描述"
    assert window._current_borehole is source
