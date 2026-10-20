"""领域数据模型。

所有模型为纯 dataclass，不依赖任何外部库。
字段使用 str 存储，与旧版文件格式保持一致，避免浮点精度问题。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .enums import TEST_SUFFIXES_BY_TYPE, HoleType

END_MARK: str = "★"

MAIN_FIELD_NAMES: list[str] = [
    "钻孔编号",
    "孔深(m)",
    "地面高程(m)",
    "钻孔地点",
    "钻孔方位、倾角",
    "比例 1:",
    "开工日期",
    "工程项目",
    "图号",
    "勘察阶段",
    "孔口坐标(x,y)",
    "竣工日期",
    "套管下入深度(m)",
    "岸上(L)或水上(W)钻进",
    "岩层产状(倾向,倾角)",
    "设计单位全称",
]

EDITABLE_MAIN_INDICES: list[int] = [0, 1, 2, 3, 5, 6, 7, 9, 11, 15]

FIXED_MAIN_DEFAULTS: dict[int, str] = {
    4: ",90",
    8: "001",
    10: "0,0",
    13: "L",
    14: ",90",
}


@dataclass
class MainFileData:
    """主文件数据，固定16行。"""

    lines: list[str] = field(default_factory=lambda: [""] * 16)

    def normalized_lines(self) -> list[str]:
        result = list(self.lines[:16])
        while len(result) < 16:
            result.append("")
        for index, value in FIXED_MAIN_DEFAULTS.items():
            if not result[index]:
                result[index] = value
        return result

    @property
    def hole_id(self) -> str:
        return self.normalized_lines()[0]

    @hole_id.setter
    def hole_id(self, value: str) -> None:
        lines = self.normalized_lines()
        lines[0] = value
        self.lines = lines

    @property
    def depth(self) -> str:
        return self.normalized_lines()[1]


@dataclass
class BasicLayer:
    """基础地层数据。"""

    bottom_depth: str = ""
    lithology_code: str = ""
    formation: str = ""
    structure: str = ""
    weathering: str = ""
    description: str = ""


@dataclass
class TestRecord:
    """试验记录。"""

    values: list[str] = field(default_factory=list)


@dataclass
class Borehole:
    """钻孔完整数据。"""

    prefix: str
    folder: Path
    hole_type: HoleType
    main: MainFileData = field(default_factory=MainFileData)
    layers: list[BasicLayer] = field(default_factory=list)
    tests: dict[str, list[TestRecord]] = field(default_factory=dict)
    raw_texts: dict[str, str] = field(default_factory=dict)
    extra_files: dict[str, str] = field(default_factory=dict)
    deleted_extra_files: set[str] = field(default_factory=set)
    existing_suffixes: set[str] = field(default_factory=set)
    is_new: bool = False
    dirty: bool = False
    dirty_suffixes: set[str] = field(default_factory=set)
    validation_messages: list[str] = field(default_factory=list)
    old_prefix: str | None = None

    def display_name(self) -> str:
        marker = "*" if self.dirty or self.is_new else ""
        return f"{marker}{self.prefix}"

    def available_test_suffixes(self) -> list[str]:
        return TEST_SUFFIXES_BY_TYPE[self.hole_type]

    def mark_dirty(self, suffix: str | None = None) -> None:
        self.dirty = True
        if suffix:
            self.dirty_suffixes.add(suffix)


@dataclass
class ProfileFile:
    """剖面文件数据。"""

    name: str
    path: Path
    content: str = ""
    extra_files: dict[str, str] = field(default_factory=dict)
    deleted_extra_files: set[str] = field(default_factory=set)
    modified: bool = False


@dataclass
class ProjectData:
    """项目数据，管理所有钻孔。"""

    folder: Path | None = None
    boreholes: dict[str, Borehole] = field(default_factory=dict)
    deleted_boreholes: dict[str, Borehole] = field(default_factory=dict)
    profile_files: dict[str, ProfileFile] = field(default_factory=dict)
    deleted_profiles: dict[str, ProfileFile] = field(default_factory=dict)
    project_files: dict[str, ProfileFile] = field(default_factory=dict)
    """项目级文件（如 0nzk.-zkt、0yzk.-zkt）。"""
    load_error: str | None = None

    def sorted_boreholes(self) -> list[Borehole]:
        def sort_key(item: Borehole) -> tuple[int, int, str]:
            type_order = 0 if item.hole_type == HoleType.ZK else 1
            digits = "".join(ch for ch in item.prefix if ch.isdigit())
            number = int(digits) if digits else 0
            return type_order, number, item.prefix

        return sorted(self.boreholes.values(), key=sort_key)

    def dirty_boreholes(self) -> list[Borehole]:
        return [b for b in self.sorted_boreholes() if b.dirty or b.is_new]
