"""Generate and synchronize managed column-chart project files."""

from __future__ import annotations

from ..domain.enums import HoleType
from ..domain.models import END_MARK, ProfileFile, ProjectData

COLUMN_CHARTS: dict[str, HoleType] = {
    "0yzk": HoleType.ZK,
    "0nzk": HoleType.NZK,
}
COLUMN_CHART_SUFFIX = "zkt"


def render_column_chart(project: ProjectData, hole_type: HoleType) -> str:
    prefixes = [hole.prefix for hole in project.sorted_boreholes() if hole.hole_type == hole_type]
    return "\n".join([*prefixes, END_MARK])


def synchronize_column_charts(project: ProjectData) -> set[str]:
    if project.folder is None:
        return set()
    folder = project.folder
    changed: set[str] = set()
    for name, hole_type in COLUMN_CHARTS.items():
        chart = project.project_files.get(name)
        if chart is None:
            chart = ProfileFile(name=name, path=folder / name)
            project.project_files[name] = chart
        expected = render_column_chart(project, hole_type)
        if chart.extra_files.get(COLUMN_CHART_SUFFIX) == expected:
            continue
        chart.extra_files[COLUMN_CHART_SUFFIX] = expected
        chart.modified = True
        changed.add(name)
    return changed
