"""领域枚举定义。"""

from __future__ import annotations

from enum import Enum


class HoleType(str, Enum):
    """钻孔类型。"""

    ZK = "ZK"
    NZK = "NZK"


class Weathering(str, Enum):
    """风化程度代码。"""

    OVERBURDEN = "f"
    FULLY_WEATHERED = "4"
    STRONGLY_WEATHERED = "3"
    WEAKLY_WEATHERED = "2"
    SLIGHTLY_WEATHERED = "1"

    @property
    def label(self) -> str:
        return {
            Weathering.OVERBURDEN: "覆盖层",
            Weathering.FULLY_WEATHERED: "全风化",
            Weathering.STRONGLY_WEATHERED: "强风化",
            Weathering.WEAKLY_WEATHERED: "弱风化",
            Weathering.SLIGHTLY_WEATHERED: "微风化",
        }[self]


WEATHERING_LABELS: dict[str, str] = {w.value: w.label for w in Weathering}
"""风化代码到中文标签的映射（兼容旧数据格式）。"""


class FileSuffix(str, Enum):
    """钻孔数据文件后缀。"""

    FORMATION = "b"
    LITHOLOGY = "c"
    STRUCTURE = "d"
    CORE_RECOVERY = "e"
    RQD = "f"
    WEATHERING = "g"
    DESCRIPTION = "h"
    WATER_LEVEL = "l"
    PERMEABILITY = "m"
    PERMEATION = "n"
    SAMPLING = "o"
    SPT = "q"


BASE_SUFFIXES: list[str] = [
    FileSuffix.FORMATION.value,
    FileSuffix.LITHOLOGY.value,
    FileSuffix.STRUCTURE.value,
    FileSuffix.WEATHERING.value,
    FileSuffix.DESCRIPTION.value,
]

ZK_TEST_SUFFIXES: list[str] = [
    FileSuffix.SAMPLING.value,
    FileSuffix.SPT.value,
    FileSuffix.PERMEABILITY.value,
    FileSuffix.PERMEATION.value,
    FileSuffix.CORE_RECOVERY.value,
    FileSuffix.RQD.value,
    FileSuffix.WATER_LEVEL.value,
]

NZK_TEST_SUFFIXES: list[str] = [
    FileSuffix.SAMPLING.value,
    FileSuffix.SPT.value,
    FileSuffix.PERMEATION.value,
    FileSuffix.WATER_LEVEL.value,
]

KNOWN_SUFFIXES: set[str] = {s.value for s in FileSuffix}

SUFFIX_NAMES: dict[str, str] = {
    FileSuffix.FORMATION.value: "地层时代",
    FileSuffix.LITHOLOGY.value: "岩性代号",
    FileSuffix.STRUCTURE.value: "钻孔结构",
    FileSuffix.WEATHERING.value: "风化程度",
    FileSuffix.DESCRIPTION.value: "岩性描述",
    FileSuffix.CORE_RECOVERY.value: "岩芯获得率",
    FileSuffix.RQD.value: "RQD值",
    FileSuffix.PERMEABILITY.value: "透水率",
    FileSuffix.PERMEATION.value: "渗透系数",
    FileSuffix.SAMPLING.value: "岩芯取样",
    FileSuffix.SPT.value: "标贯击数",
    FileSuffix.WATER_LEVEL.value: "稳定水位",
}

TEST_SUFFIXES_BY_TYPE: dict[HoleType, list[str]] = {
    HoleType.ZK: ZK_TEST_SUFFIXES,
    HoleType.NZK: NZK_TEST_SUFFIXES,
}
