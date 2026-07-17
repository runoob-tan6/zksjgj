from pathlib import Path

from borehole.application.column_chart_service import synchronize_column_charts
from borehole.application.project_service import create_new_borehole
from borehole.domain.models import ProfileFile, ProjectData


def test_sync_creates_both_column_charts_with_natural_hole_order(tmp_path: Path) -> None:
    project = ProjectData(folder=tmp_path)
    for prefix in ("ZK10", "NZK2", "ZK2", "NZK1"):
        create_new_borehole(project, prefix)

    changed = synchronize_column_charts(project)

    assert changed == {"0yzk", "0nzk"}
    assert project.project_files["0yzk"].extra_files["zkt"] == "ZK2\nZK10\n★"
    assert project.project_files["0nzk"].extra_files["zkt"] == "NZK1\nNZK2\n★"
    assert project.project_files["0yzk"].modified
    assert project.project_files["0nzk"].modified


def test_sync_creates_empty_chart_and_keeps_unrelated_project_file(tmp_path: Path) -> None:
    unrelated = ProfileFile(name="0other", path=tmp_path / "0other")
    unrelated.extra_files["cfg"] = "keep"
    project = ProjectData(folder=tmp_path, project_files={"0other": unrelated})

    synchronize_column_charts(project)

    assert project.project_files["0yzk"].extra_files["zkt"] == "★"
    assert project.project_files["0nzk"].extra_files["zkt"] == "★"
    assert project.project_files["0other"] is unrelated


def test_sync_does_not_dirty_canonical_existing_charts(tmp_path: Path) -> None:
    project = ProjectData(folder=tmp_path)
    create_new_borehole(project, "ZK1")
    project.project_files = {
        "0yzk": ProfileFile(
            name="0yzk", path=tmp_path / "0yzk", extra_files={"zkt": "ZK1\n★"}
        ),
        "0nzk": ProfileFile(name="0nzk", path=tmp_path / "0nzk", extra_files={"zkt": "★"}),
    }

    changed = synchronize_column_charts(project)

    assert changed == set()
    assert not project.project_files["0yzk"].modified
    assert not project.project_files["0nzk"].modified
