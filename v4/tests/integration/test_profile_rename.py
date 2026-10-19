import os
from pathlib import Path

import pytest

from borehole.application.project_service import load_project
from borehole.application.save_service import SaveService
from borehole.infrastructure.save_transaction import SaveTransactionError


def _write_profile_group(folder: Path, name: str) -> None:
    (folder / name).write_text("剖面主文件\n★", encoding="gbk", newline="")
    for suffix in ("d0", "g", "k"):
        (folder / f"{name}.-{suffix}").write_text(f"附属-{suffix}\n★", encoding="gbk", newline="")
    (folder / "0yzk.-zkt").write_text("★", encoding="utf-8", newline="")
    (folder / "0nzk.-zkt").write_text("★", encoding="utf-8", newline="")


def _rename_in_model(project, old_name: str, new_name: str):
    profile = project.profile_files.pop(old_name)
    profile.old_name = old_name
    profile.name = new_name
    profile.path = project.folder / new_name
    profile.modified = True
    project.profile_files[new_name] = profile
    return profile


def test_save_renames_complete_profile_group(tmp_path: Path) -> None:
    _write_profile_group(tmp_path, "H8")
    project = load_project(tmp_path)
    profile = _rename_in_model(project, "H8", "H9")

    SaveService(project).save()

    for name in ("H9", "H9.-d0", "H9.-g", "H9.-k"):
        assert (tmp_path / name).exists()
    for name in ("H8", "H8.-d0", "H8.-g", "H8.-k"):
        assert not (tmp_path / name).exists()
    assert (tmp_path / "H9").read_text(encoding="gbk") == "剖面主文件\n★"
    assert (tmp_path / "H9.-d0").read_text(encoding="gbk") == "附属-d0\n★"
    assert profile.old_name is None


def test_profile_rename_failure_restores_old_group_and_keeps_dirty_state(tmp_path: Path, monkeypatch) -> None:
    _write_profile_group(tmp_path, "H8")
    project = load_project(tmp_path)
    profile = _rename_in_model(project, "H8", "H9")
    real_replace = os.replace
    calls = 0

    def fail_second_replace(source: str | Path, target: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected profile rename failure")
        real_replace(source, target)

    monkeypatch.setattr("borehole.infrastructure.save_transaction.os.replace", fail_second_replace)

    with pytest.raises(SaveTransactionError, match="injected profile rename failure"):
        SaveService(project).save()

    for name in ("H8", "H8.-d0", "H8.-g", "H8.-k"):
        assert (tmp_path / name).exists()
    for name in ("H9", "H9.-d0", "H9.-g", "H9.-k"):
        assert not (tmp_path / name).exists()
    assert profile.modified
    assert profile.old_name == "H8"
