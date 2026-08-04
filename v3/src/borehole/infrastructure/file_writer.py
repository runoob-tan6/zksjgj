"""文件写入器 - 将领域模型序列化为磁盘文件。"""

from __future__ import annotations

from collections.abc import Iterable

from ..domain.models import END_MARK, MAIN_INDEX_CASING_DEPTH, MAIN_INDEX_DEPTH, Borehole


def make_file_text(lines: Iterable[str]) -> str:
    clean = [str(line) for line in lines]
    return "\n".join([*clean, END_MARK])


def render_main_file(borehole: Borehole) -> str:
    lines = borehole.main.normalized_lines()
    lines[MAIN_INDEX_CASING_DEPTH] = lines[MAIN_INDEX_DEPTH]
    return make_file_text(lines)


def render_pair_file(rows: list[tuple[str, str]], skip_empty_value: bool = False) -> str:
    lines = []
    for depth, value in rows:
        depth = str(depth or "").strip()
        value = str(value or "").strip()
        if skip_empty_value and not value:
            continue
        if depth or value:
            lines.append(f"{depth},{value}")
    return make_file_text(lines)


def render_h_file(borehole: Borehole) -> str:
    lines: list[str] = []
    for layer in borehole.layers:
        depth = str(layer.bottom_depth or "").strip()
        description = str(layer.description or "").strip()
        if depth and description:
            lines.extend((f"#{depth}", description))
    return make_file_text(lines)


def build_test_file_lines(borehole: Borehole, suffix: str) -> list[str]:
    lines = []
    value_limit = 2 if suffix in {"e", "f"} else None
    for record in borehole.tests.get(suffix, []):
        raw_values = record.values[:value_limit] if value_limit else record.values
        values = [str(value or "").strip() for value in raw_values]
        while values and not values[-1]:
            values.pop()
        if any(values):
            lines.append(",".join(values))
    return lines


def render_test_file(borehole: Borehole, suffix: str) -> str:
    return make_file_text(build_test_file_lines(borehole, suffix))
