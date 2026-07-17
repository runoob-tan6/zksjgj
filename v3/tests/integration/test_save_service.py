from pathlib import Path

import pytest

from borehole.application.project_service import load_project
from borehole.application.save_service import SaveService
from borehole.infrastructure.save_transaction import SaveTransactionError


def test_save_service_commits_borehole_profile_and_project_files(legacy_project: Path) -> None:
    project = load_project(legacy_project)
    borehole = project.boreholes["ZK1"]
    borehole.layers[0].lithology_code = "33"
    borehole.mark_dirty("c")
    profile = project.profile_files["H1"]
    profile.content = "更新的剖面\n★"
    profile.modified = True
    project_file = project.project_files["0nzk"]
    project_file.extra_files["zkt"] = "更新的配置\n"
    project_file.modified = True

    result = SaveService(project).save()

    assert result.generated == [legacy_project / "ZK1.-c"]
    assert result.profile_count == 3
    assert not borehole.dirty
    assert not profile.modified
    assert not project_file.modified
    assert "5.0,33" in (legacy_project / "ZK1.-c").read_text(encoding="gbk")
    assert "更新的剖面" in (legacy_project / "H1").read_text(encoding="gbk")
    assert (legacy_project / "0nzk.-zkt").read_text(encoding="gbk") == "★"
    assert (legacy_project / "0yzk.-zkt").read_text(encoding="utf-8") == "ZK1\n★"


def test_save_service_keeps_dirty_state_when_transaction_fails(legacy_project: Path, monkeypatch) -> None:
    project = load_project(legacy_project)
    borehole = project.boreholes["ZK1"]
    original = (legacy_project / "ZK1.-c").read_bytes()
    borehole.layers[0].lithology_code = "99"
    borehole.mark_dirty("c")

    def fail_commit(_self) -> None:
        raise SaveTransactionError("injected failure")

    monkeypatch.setattr("borehole.application.save_service.SaveTransaction.commit", fail_commit)

    with pytest.raises(SaveTransactionError, match="injected failure"):
        SaveService(project).save()

    assert borehole.dirty
    assert borehole.dirty_suffixes == {"c"}
    assert (legacy_project / "ZK1.-c").read_bytes() == original
