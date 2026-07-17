from pathlib import Path

from borehole.application.project_service import load_project
from borehole.infrastructure.file_writer import generate_borehole, write_with_backup


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
    borehole = project.boreholes["ZK1"]
    before = _snapshot(legacy_project)
    borehole.layers[0].lithology_code = "33"
    borehole.mark_dirty("c")

    changed = generate_borehole(borehole)

    assert changed == [legacy_project / "ZK1.-c"]
    after = _snapshot(legacy_project)
    assert {name for name in before if before[name] != after[name]} == {"ZK1.-c"}
    assert (legacy_project / "ZK1.-x").read_bytes() == before["ZK1.-x"]


def test_write_with_backup_preserves_gbk_and_crlf(tmp_path: Path) -> None:
    target = tmp_path / "ZK1"
    target.write_bytes("旧值\r\n★".encode("gbk"))

    changed = write_with_backup(target, "新值\n★", tmp_path / "tmp")

    assert changed
    assert target.read_bytes() == "新值\r\n★".encode("gbk")
    assert len(list((tmp_path / "tmp").glob("ZK1.*.bak"))) == 1


def test_write_with_backup_preserves_lf(tmp_path: Path) -> None:
    target = tmp_path / "ZK1"
    target.write_bytes("old\n★".encode())

    write_with_backup(target, "new\n★", tmp_path / "tmp")

    assert target.read_bytes() == b"new\n\xe2\x98\x85"
