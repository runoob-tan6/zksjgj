"""钻孔数据编辑工具 - 数据模型模块。

本模块定义了钻孔数据编辑工具的核心数据结构，包括：
- 主文件数据（MainFileData）
- 基础地层（BasicLayer）
- 试验记录（TestRecord）
- 钻孔（Borehole）
- 项目数据（ProjectData）

所有数据类使用 @dataclass 装饰器，提供简洁的数据容器实现。

典型用法：
    >>> from borehole_app.models import Borehole, MainFileData
    >>> borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
    >>> borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ============================================================================
# 常量定义
# ============================================================================

END_MARK: str = "★"
"""文件结束标记符号。"""

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
"""主文件字段名称列表，共16个字段。"""

EDITABLE_MAIN_INDICES: list[int] = [0, 1, 2, 3, 5, 6, 7, 9, 11, 15]
"""主文件中可编辑字段的索引列表。"""

FIXED_MAIN_DEFAULTS: dict[int, str] = {
    4: ",90",
    8: "001",
    10: "0,0",
    13: "L",
    14: ",90",
}
"""主文件中固定字段的默认值映射。"""

WEATHERING_MAP: dict[str, str] = {
    "f": "覆盖层",
    "4": "全风化",
    "3": "强风化",
    "2": "弱风化",
    "1": "微风化",
}
"""风化程度代码到中文名称的映射。"""

BASE_SUFFIXES: list[str] = ["b", "c", "d", "g", "h"]
"""基础数据文件后缀列表。"""

ZK_TEST_SUFFIXES: list[str] = ["o", "q", "m", "n", "e", "f", "l"]
"""岩钻孔(ZK)试验数据文件后缀列表。"""

NZK_TEST_SUFFIXES: list[str] = ["o", "q", "n", "l"]
"""土钻孔(NZK)试验数据文件后缀列表。"""

TEST_SUFFIX_NAMES: dict[str, str] = {
    "e": "岩芯获得率",
    "f": "RQD值",
    "m": "透水率",
    "n": "渗透系数",
    "o": "岩芯取样",
    "q": "标贯击数",
    "l": "稳定水位",
}
"""试验数据文件后缀到中文名称的映射。"""

BASE_SUFFIX_NAMES: dict[str, str] = {
    "b": "地层时代",
    "c": "岩性代号",
    "d": "钻孔结构",
    "g": "风化程度",
    "h": "岩性描述",
}
"""基础数据文件后缀到中文名称的映射。"""


# ============================================================================
# 数据类定义
# ============================================================================


@dataclass
class MainFileData:
    """主文件数据类，存储钻孔主文件的16行内容。

    主文件包含钻孔的基本信息，如编号、孔深、坐标等。
    固定为16行，每行对应一个字段。

    Attributes:
        lines: 主文件的16行内容列表

    Example:
        >>> data = MainFileData(lines=["ZK1", "10.5"] + [""] * 14)
        >>> data.hole_id
        'ZK1'
        >>> data.depth
        '10.5'
    """

    lines: list[str] = field(default_factory=lambda: [""] * 16)

    def normalized_lines(self) -> list[str]:
        """获取标准化的主文件行内容。

        确保返回16行内容，空字段填充默认值。

        Returns:
            包含16个元素的字符串列表，空字段已填充默认值

        Example:
            >>> data = MainFileData(lines=["ZK1", "10"])
            >>> lines = data.normalized_lines()
            >>> len(lines)
            16
            >>> lines[0]
            'ZK1'
        """
        result = list(self.lines[:16])
        while len(result) < 16:
            result.append("")
        for index, value in FIXED_MAIN_DEFAULTS.items():
            if not result[index]:
                result[index] = value
        return result

    @property
    def hole_id(self) -> str:
        """获取钻孔编号。

        Returns:
            钻孔编号字符串，为空字符串时表示未设置

        Example:
            >>> data = MainFileData(lines=["ZK1", "10"] + [""] * 14)
            >>> data.hole_id
            'ZK1'
        """
        return self.normalized_lines()[0]

    @hole_id.setter
    def hole_id(self, value: str) -> None:
        """设置钻孔编号。

        Args:
            value: 新的钻孔编号
        """
        lines = self.normalized_lines()
        lines[0] = value
        self.lines = lines

    @property
    def depth(self) -> str:
        """获取钻孔深度。

        Returns:
            钻孔深度字符串，为空字符串时表示未设置

        Example:
            >>> data = MainFileData(lines=["ZK1", "10.5"] + [""] * 14)
            >>> data.depth
            '10.5'
        """
        return self.normalized_lines()[1]


@dataclass
class BasicLayer:
    """基础地层数据类，存储单个地层的基本信息。

    每个地层包含层底深度、岩性代号、地层时代等信息。

    Attributes:
        bottom_depth: 层底深度(m)
        lithology_code: 岩性代号
        formation: 地层时代
        structure: 钻孔结构
        weathering: 风化程度代码
        description: 岩性描述

    Example:
        >>> layer = BasicLayer(bottom_depth="5", lithology_code="A", formation="Q")
        >>> layer.bottom_depth
        '5'
    """

    bottom_depth: str = ""
    lithology_code: str = ""
    formation: str = ""
    structure: str = ""
    weathering: str = ""
    description: str = ""


@dataclass
class TestRecord:
    """试验记录数据类，存储单条试验数据。

    试验记录包含多个值，具体含义取决于试验类型。

    Attributes:
        values: 试验数据值列表，具体含义由试验类型决定

    Example:
        >>> record = TestRecord(values=["1", "5", "0.000409"])
        >>> len(record.values)
        3
    """

    values: list[str] = field(default_factory=list)


@dataclass
class Borehole:
    """钻孔数据类，存储单个钻孔的完整信息。

    包含钻孔的基本信息、地层数据、试验数据等。
    支持ZK（岩钻孔）和NZK（土钻孔）两种类型。

    Attributes:
        prefix: 钻孔编号前缀（如"ZK1"）
        folder: 钻孔数据文件夹路径
        hole_type: 钻孔类型，"ZK"或"NZK"
        main: 主文件数据
        layers: 地层列表
        tests: 试验数据字典，键为后缀，值为记录列表
        raw_texts: 原始文本字典，键为后缀，值为文件内容
        existing_suffixes: 已存在的文件后缀集合
        is_new: 是否为新建钻孔
        dirty: 是否有未保存的修改
        dirty_suffixes: 有修改的文件后缀集合
        validation_messages: 校验消息列表
        old_prefix: 编号变更前的旧前缀

    Example:
        >>> borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        >>> borehole.display_name()
        '*ZK1'  # 新建钻孔显示*标记
    """

    prefix: str
    folder: Path
    hole_type: str
    main: MainFileData = field(default_factory=MainFileData)
    layers: list[BasicLayer] = field(default_factory=list)
    tests: dict[str, list[TestRecord]] = field(default_factory=dict)
    raw_texts: dict[str, str] = field(default_factory=dict)
    existing_suffixes: set[str] = field(default_factory=set)
    is_new: bool = False
    dirty: bool = False
    dirty_suffixes: set[str] = field(default_factory=set)
    validation_messages: list[str] = field(default_factory=list)
    old_prefix: str | None = None

    def display_name(self) -> str:
        """获取钻孔显示名称。

        新建或有未保存修改的钻孔会在名称前添加*标记。

        Returns:
            格式化的钻孔显示名称

        Example:
            >>> borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
            >>> borehole.display_name()
            '*ZK1'  # 新建钻孔
            >>> borehole.is_new = False
            >>> borehole.display_name()
            'ZK1'   # 已保存钻孔
        """
        marker = "*" if self.dirty or self.is_new else ""
        return f"{marker}{self.prefix}"

    def available_test_suffixes(self) -> list[str]:
        """获取当前钻孔类型可用的试验数据后缀列表。

        Returns:
            试验数据后缀列表

        Example:
            >>> borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
            >>> "e" in borehole.available_test_suffixes()
            True
            >>> borehole = Borehole(prefix="NZK1", folder=Path("/data"), hole_type="NZK")
            >>> "e" in borehole.available_test_suffixes()
            False
        """
        return ZK_TEST_SUFFIXES if self.hole_type == "ZK" else NZK_TEST_SUFFIXES

    def mark_dirty(self, suffix: str | None = None) -> None:
        """标记钻孔为已修改状态。

        Args:
            suffix: 修改的文件后缀，为None时只标记整体dirty

        Example:
            >>> borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
            >>> borehole.mark_dirty("c")
            >>> borehole.dirty
            True
            >>> "c" in borehole.dirty_suffixes
            True
        """
        self.dirty = True
        if suffix:
            self.dirty_suffixes.add(suffix)


@dataclass
class ProjectData:
    """项目数据类，管理整个钻孔项目。

    包含项目文件夹路径、所有钻孔数据、已删除钻孔等信息。

    Attributes:
        folder: 项目文件夹路径
        boreholes: 钻孔字典，键为钻孔编号，值为Borehole对象
        deleted_boreholes: 已删除钻孔字典
        load_error: 加载错误信息

    Example:
        >>> project = ProjectData(folder=Path("/project"))
        >>> borehole = Borehole(prefix="ZK1", folder=Path("/project/ZK1"), hole_type="ZK")
        >>> project.boreholes["ZK1"] = borehole
        >>> len(project.sorted_boreholes())
        1
    """

    folder: Path | None = None
    boreholes: dict[str, Borehole] = field(default_factory=dict)
    deleted_boreholes: dict[str, Borehole] = field(default_factory=dict)
    load_error: str | None = None

    def sorted_boreholes(self) -> list[Borehole]:
        """获取按类型和编号排序的钻孔列表。

        排序规则：
        1. ZK类型在前，NZK类型在后
        2. 同类型按编号中的数字排序
        3. 数字相同按完整编号排序

        Returns:
            排序后的钻孔列表

        Example:
            >>> project = ProjectData(folder=Path("/project"))
            >>> # 添加多个钻孔...
            >>> sorted_list = project.sorted_boreholes()
            >>> # ZK类型在前，NZK类型在后
        """

        def sort_key(item: Borehole) -> tuple[int, int, str]:
            type_order = 0 if item.hole_type == "ZK" else 1
            digits = "".join(ch for ch in item.prefix if ch.isdigit())
            number = int(digits) if digits else 0
            return type_order, number, item.prefix

        return sorted(self.boreholes.values(), key=sort_key)

    def dirty_boreholes(self) -> list[Borehole]:
        """获取有未保存修改的钻孔列表。

        Returns:
            有修改的钻孔列表，按排序规则排列

        Example:
            >>> project = ProjectData(folder=Path("/project"))
            >>> # 修改一些钻孔...
            >>> dirty_list = project.dirty_boreholes()
            >>> # 只返回有修改的钻孔
        """
        return [b for b in self.sorted_boreholes() if b.dirty or b.is_new]
