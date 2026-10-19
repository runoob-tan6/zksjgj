from pathlib import Path

from borehole.infrastructure import settings


def test_settings_path_is_resolved_at_call_time(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "get_app_base_dir", lambda: tmp_path)
    project = tmp_path / "项目"

    assert settings.save_last_project(project)

    assert settings.load_last_project() == project
    assert (tmp_path / ".Data" / "app_settings.json").exists()


def test_save_last_project_degrades_when_settings_location_is_not_writable(tmp_path: Path, monkeypatch) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("file", encoding="utf-8")
    monkeypatch.setattr(settings, "get_app_base_dir", lambda: blocked)

    assert not settings.save_last_project(tmp_path / "project")
