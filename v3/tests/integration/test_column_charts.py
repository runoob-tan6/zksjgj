from pathlib import Path

from borehole.application.project_service import load_project


def _write_main(folder: Path, prefix: str) -> None:
    lines = [prefix, "10", "100", "", ",90", "100", "", "", "001", "", "0,0", "", "10", "L", ",90", "", "★"]
    (folder / prefix).write_text("\n".join(lines), encoding="utf-8", newline="")


def _snapshot(folder: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in folder.iterdir() if path.is_file()}


def test_load_creates_missing_column_charts_in_memory_without_writing(tmp_path: Path) -> None:
    _write_main(tmp_path, "ZK10")
    _write_main(tmp_path, "ZK2")
    _write_main(tmp_path, "NZK1")
    before = _snapshot(tmp_path)

    project = load_project(tmp_path)

    assert _snapshot(tmp_path) == before
    assert project.project_files["0yzk"].extra_files["zkt"] == "ZK2\nZK10\n★"
    assert project.project_files["0nzk"].extra_files["zkt"] == "NZK1\n★"
    assert project.project_files["0yzk"].modified
    assert project.project_files["0nzk"].modified


def test_load_keeps_canonical_existing_column_charts_clean(tmp_path: Path) -> None:
    _write_main(tmp_path, "ZK1")
    (tmp_path / "0yzk.-zkt").write_text("ZK1\n★", encoding="utf-8", newline="")
    (tmp_path / "0nzk.-zkt").write_text("★", encoding="utf-8", newline="")

    project = load_project(tmp_path)

    assert not project.project_files["0yzk"].modified
    assert not project.project_files["0nzk"].modified
