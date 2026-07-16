from pathlib import Path

from borehole.domain.models import ProjectData
from borehole.infrastructure.xlsx_export import export_layer_test_summary


def test_export_sorts_project_once(tmp_path: Path) -> None:
    project = ProjectData(folder=tmp_path)
    original = project.sorted_boreholes
    calls = 0

    def counted_sort():
        nonlocal calls
        calls += 1
        return original()

    project.sorted_boreholes = counted_sort  # type: ignore[method-assign]

    export_layer_test_summary(project, tmp_path / "summary.csv")

    assert calls == 1
