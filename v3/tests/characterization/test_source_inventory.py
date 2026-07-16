import inspect
from pathlib import Path

from borehole.ui.main_window import MainWindow

EXPECTED_MODULES = {
    "__init__.py",
    "application/__init__.py",
    "application/project_service.py",
    "application/undo_manager.py",
    "domain/__init__.py",
    "domain/enums.py",
    "domain/models.py",
    "domain/validators.py",
    "infrastructure/__init__.py",
    "infrastructure/file_parser.py",
    "infrastructure/file_writer.py",
    "infrastructure/settings.py",
    "infrastructure/spt_analysis.py",
    "infrastructure/table_importer.py",
    "infrastructure/xlsx_export.py",
    "main.py",
    "ui/__init__.py",
    "ui/basic_data_page.py",
    "ui/format_utils.py",
    "ui/info_pages.py",
    "ui/main_file_page.py",
    "ui/main_window.py",
    "ui/spt_analysis_page.py",
    "ui/test_data_page.py",
}

EXPECTED_MAIN_WINDOW_COMMANDS = {
    "_add_borehole",
    "_add_extra_file",
    "_add_profile",
    "_add_project_file",
    "_check_unsaved_changes",
    "_choose_project",
    "_copy_borehole",
    "_copy_profile",
    "_delete_borehole",
    "_delete_extra_file",
    "_delete_profile",
    "_delete_profile_extra",
    "_delete_project_file",
    "_export_layer_tests",
    "_import_table_file",
    "_open_project_folder",
    "_redo",
    "_reload_project",
    "_save_data",
    "_sync_description",
    "_undo",
    "_validate_project",
    "closeEvent",
    "dragEnterEvent",
    "dropEvent",
}


def test_v3_keeps_every_v2_source_module() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src" / "borehole"
    actual = {path.relative_to(source_root).as_posix() for path in source_root.rglob("*.py")}

    assert EXPECTED_MODULES <= actual


def test_v3_keeps_every_v2_main_window_command() -> None:
    actual = {name for name, member in inspect.getmembers(MainWindow, inspect.isfunction)}

    assert EXPECTED_MAIN_WINDOW_COMMANDS <= actual
