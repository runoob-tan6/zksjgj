"""文件解析器 - 从磁盘读取钻孔数据文件并转换为领域模型。"""

from __future__ import annotations

from pathlib import Path

from ..domain.enums import HoleType
from ..domain.models import (
    END_MARK,
    BasicLayer,
    Borehole,
    MainFileData,
    TestRecord,
)
from .text_io import read_text_auto


def read_text_file(path: Path) -> str:
    """读取文本文件，自动检测编码。"""
    result = read_text_auto(path)
    return result.text or ""


def clean_lines(text: str) -> list[str]:
    return [line.rstrip("\r\n") for line in text.splitlines()]


def data_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = clean_lines(read_text_file(path))
    return [line for line in lines if line != END_MARK and line != ""]


def main_file_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = clean_lines(read_text_file(path))
    return [line for line in lines if line != END_MARK]


def parse_main_file(path: Path) -> MainFileData:
    lines = main_file_lines(path)
    while len(lines) < 16:
        lines.append("")
    return MainFileData(lines=lines[:16])


def parse_pair_file(path: Path) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for line in data_lines(path):
        parts = line.split(",", 1)
        if len(parts) == 2:
            result.append((parts[0].strip(), parts[1].strip()))
    return result


def parse_h_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    lines = data_lines(path)
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if line.startswith("#"):
            depth = line[1:].strip()
            description = ""
            if index + 1 < len(lines) and not lines[index + 1].strip().startswith("#"):
                description = lines[index + 1].strip()
                index += 2
            else:
                index += 1
            result[depth] = description
        else:
            index += 1
    return result


def parse_test_file(path: Path) -> list[TestRecord]:
    records: list[TestRecord] = []
    for line in data_lines(path):
        values = [part.strip() for part in line.split(",")]
        if values:
            records.append(TestRecord(values=values))
    return records


def _depth_key(value: str) -> tuple[int, float | str]:
    try:
        return (0, float(value))
    except ValueError:
        return (1, value)


def parse_basic_layers(folder: Path, prefix: str) -> list[BasicLayer]:
    c_pairs = parse_pair_file(folder / f"{prefix}.-c")
    b_map = dict(parse_pair_file(folder / f"{prefix}.-b"))
    d_map = dict(parse_pair_file(folder / f"{prefix}.-d"))
    g_map = dict(parse_pair_file(folder / f"{prefix}.-g"))
    h_map = parse_h_file(folder / f"{prefix}.-h")
    layers: list[BasicLayer] = []
    for depth, lithology in c_pairs:
        layers.append(
            BasicLayer(
                bottom_depth=depth,
                lithology_code=lithology,
                formation=b_map.get(depth, ""),
                structure=d_map.get(depth, ""),
                weathering=g_map.get(depth, ""),
                description=h_map.get(depth, ""),
            )
        )
    if not layers:
        all_depths = sorted(set(b_map) | set(d_map) | set(g_map) | set(h_map), key=_depth_key)
        for depth in all_depths:
            layers.append(
                BasicLayer(
                    bottom_depth=depth,
                    formation=b_map.get(depth, ""),
                    structure=d_map.get(depth, ""),
                    weathering=g_map.get(depth, ""),
                    description=h_map.get(depth, ""),
                )
            )
    return layers


def parse_borehole(folder: Path, prefix: str, files: dict[str, Path]) -> Borehole:
    hole_type = HoleType.NZK if prefix.upper().startswith("NZK") else HoleType.ZK
    borehole = Borehole(prefix=prefix, folder=folder, hole_type=hole_type)
    main_path = folder / prefix
    if main_path.exists():
        borehole.main = parse_main_file(main_path)
        borehole.raw_texts["主文件"] = read_text_file(main_path)
        borehole.existing_suffixes.add("main")
    for suffix, path in files.items():
        if path.exists():
            borehole.raw_texts[f".-{suffix}"] = read_text_file(path)
            borehole.existing_suffixes.add(suffix)
    borehole.layers = parse_basic_layers(folder, prefix)
    for suffix in borehole.available_test_suffixes():
        path = folder / f"{prefix}.-{suffix}"
        borehole.tests[suffix] = parse_test_file(path)
    return borehole
