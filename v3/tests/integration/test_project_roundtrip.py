from pathlib import Path

from borehole.application.project_service import load_project
from borehole.application.save_service import SaveService


def _snapshot(folder: Path) -> dict[str, bytes]:
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in folder.rglob("*") if path.is_file()}


def test_loading_legacy_project_does_not_change_any_bytes(legacy_project: Path) -> None:
    before = _snapshot(legacy_project)

    project = load_project(legacy_project)

    assert _snapshot(legacy_project) == before
    assert list(project.boreholes) == ["ZK1"]
    assert project.boreholes["ZK1"].main.depth == "12.5"
    assert [layer.lithology_code for layer in project.boreholes["ZK1"].layers] == ["11", "22"]
    assert project.boreholes["ZK1"].tests["q"][0].values == ["2.0", "2.3", "8"]
    assert project.boreholes["ZK1"].extra_files["x"] == "保留的未知文件\n"
    assert project.profile_files["H1"].extra_files["x"] == "剖面附属文件\n"
    assert project.project_files["0yzk"].extra_files["zkt"] == "ZK1\n★"
    assert project.project_files["0nzk"].extra_files["zkt"] == "★"
    assert project.project_files["0yzk"].modified
    assert project.project_files["0nzk"].modified


def test_editing_one_layer_only_changes_requested_file(legacy_project: Path) -> None:
    project = load_project(legacy_project)
    SaveService(project).save()
    borehole = project.boreholes["ZK1"]
    before = _snapshot(legacy_project)
    borehole.layers[0].lithology_code = "33"
    borehole.mark_dirty("c")

    result = SaveService(project).save()

    assert result.generated == [legacy_project / "ZK1.-c"]
    after = _snapshot(legacy_project)
    assert {name for name in before if before[name] != after[name]} == {"ZK1.-c"}
    assert (legacy_project / "ZK1.-x").read_bytes() == before["ZK1.-x"]


def test_save_service_preserves_gbk_and_crlf(legacy_project: Path) -> None:
    target = legacy_project / "ZK1"
    project = load_project(legacy_project)
    borehole = project.boreholes["ZK1"]
    borehole.main.lines[3] = "新地点"
    borehole.mark_dirty("main")

    result = SaveService(project).save()

    content = target.read_bytes()
    assert result.generated == [target]
    assert "新地点" in content.decode("gbk")
    assert b"\r\n" in content
    assert len(list((legacy_project / "tmp").glob("ZK1.*.bak"))) == 1


def test_save_service_preserves_utf8_and_lf(legacy_project: Path) -> None:
    target = legacy_project / "ZK1"
    original = target.read_text(encoding="gbk")
    target.write_text(original, encoding="utf-8", newline="\n")
    project = load_project(legacy_project)
    borehole = project.boreholes["ZK1"]
    borehole.main.lines[3] = "new place"
    borehole.mark_dirty("main")

    SaveService(project).save()

    content = target.read_bytes()
    assert b"new place" in content
    assert b"\r\n" not in content
    assert content.decode("utf-8").endswith("\n★")
