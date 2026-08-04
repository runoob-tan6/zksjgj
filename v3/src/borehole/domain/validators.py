"""领域校验规则。"""

from __future__ import annotations

from .enums import WEATHERING_LABELS, HoleType
from .models import MAIN_INDEX_DEPTH, MAIN_INDEX_HOLE_ID, Borehole, ProjectData


def _pair_depths(raw_text: str) -> list[str]:
    depths: list[str] = []
    for line in raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line or line == "★" or "," not in line:
            continue
        depth = line.split(",", 1)[0].strip()
        if depth:
            depths.append(depth)
    return depths


def _h_depths(raw_text: str) -> list[str]:
    depths: list[str] = []
    for line in raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if line.startswith("#"):
            depth = line[1:].strip()
            if depth:
                depths.append(depth)
    return depths


def _duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def validate_borehole(borehole: Borehole) -> list[str]:
    """校验单个钻孔数据完整性。"""
    messages: list[str] = []
    lines = borehole.main.normalized_lines()

    if not lines[MAIN_INDEX_HOLE_ID]:
        messages.append("主文件缺少钻孔编号。")
    if not lines[MAIN_INDEX_DEPTH]:
        messages.append("主文件缺少孔深。")

    try:
        hole_depth = float(lines[MAIN_INDEX_DEPTH]) if lines[MAIN_INDEX_DEPTH] else None
    except ValueError:
        hole_depth = None
        messages.append(f"孔深不是有效数字：{lines[MAIN_INDEX_DEPTH]}")

    previous = 0.0
    for index, layer in enumerate(borehole.layers, start=1):
        if not layer.bottom_depth:
            messages.append(f"第 {index} 层缺少层底深度。")
            continue
        try:
            depth = float(layer.bottom_depth)
        except ValueError:
            messages.append(f"第 {index} 层层底深度不是有效数字：{layer.bottom_depth}")
            continue
        if depth <= previous:
            messages.append(f"第 {index} 层层底深度未递增。")
        previous = depth
        if not layer.lithology_code:
            messages.append(f"第 {index} 层缺少岩性代号。")
        if layer.weathering and layer.weathering not in WEATHERING_LABELS:
            messages.append(f"第 {index} 层风化代码无效：{layer.weathering}")

    if hole_depth is not None and borehole.layers:
        try:
            last_depth = float(borehole.layers[-1].bottom_depth)
            if abs(last_depth - hole_depth) > 0.01:
                messages.append(f"最后层底深度 {last_depth:g} 与孔深 {hole_depth:g} 不一致。")
        except ValueError:
            pass

    c_depths = {layer.bottom_depth for layer in borehole.layers if layer.bottom_depth}
    for suffix in ("b", "d", "g"):
        raw_text = borehole.raw_texts.get(f".-{suffix}")
        if not raw_text:
            continue
        extra_depths = [depth for depth in _pair_depths(raw_text) if depth not in c_depths]
        if extra_depths:
            messages.append(f".-{suffix} 存在未匹配 .-c 的深度：{', '.join(extra_depths)}")

    h_raw_text = borehole.raw_texts.get(".-h")
    if h_raw_text:
        h_depths = _h_depths(h_raw_text)
        extra_h_depths = [depth for depth in h_depths if depth not in c_depths]
        if extra_h_depths:
            messages.append(f".-h 存在未匹配 .-c 的深度：{', '.join(extra_h_depths)}")
        duplicate_h_depths = _duplicate_values(h_depths)
        if duplicate_h_depths:
            messages.append(f".-h 存在重复深度：{', '.join(duplicate_h_depths)}")

    if borehole.hole_type == HoleType.NZK:
        for suffix in ("e", "f", "m"):
            if borehole.tests.get(suffix):
                messages.append(f"NZK 土钻孔不应有 .-{suffix} 试验数据。")

    return messages


def validate_project(project: ProjectData) -> list[str]:
    """校验整个项目。"""
    messages: list[str] = []
    for borehole in project.sorted_boreholes():
        for message in validate_borehole(borehole):
            messages.append(f"{borehole.prefix}: {message}")
    return messages
