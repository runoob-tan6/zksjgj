"""钻孔数据编辑工具 - 数据校验模块。

本模块负责校验钻孔数据的完整性和正确性，包括：
- 主文件字段校验
- 地层深度递增校验
- 岩性代号完整性校验
- 风化代码有效性校验
- 孔深与层底深度一致性校验
- 基础文件深度匹配校验
- 岩性描述重复深度校验
- 土钻孔试验类型校验

典型用法：
    >>> from borehole_app.validation import validate_borehole
    >>> messages = validate_borehole(borehole)
    >>> if messages:
    ...     print("校验发现问题：")
    ...     for msg in messages:
    ...         print(f"  - {msg}")
"""

from __future__ import annotations

from .models import WEATHERING_MAP, Borehole, ProjectData


def _pair_depths(raw_text: str) -> list[str]:
    """从配对格式文本中提取深度列表。

    配对格式：每行 "深度,值"，以逗号分隔。

    Args:
        raw_text: 原始文本内容

    Returns:
        深度值列表

    Example:
        >>> depths = _pair_depths("5,A\\n10,B\\n★")
        >>> depths
        ['5', '10']
    """
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
    """从岩性描述文本中提取深度列表。

    岩性描述格式：以 # 开头的行表示深度。

    Args:
        raw_text: 原始文本内容

    Returns:
        深度值列表

    Example:
        >>> depths = _h_depths("#5\\n描述1\\n#10\\n描述2\\n★")
        >>> depths
        ['5', '10']
    """
    depths: list[str] = []
    for line in raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if line.startswith("#"):
            depth = line[1:].strip()
            if depth:
                depths.append(depth)
    return depths


def _duplicate_values(values: list[str]) -> list[str]:
    """找出列表中的重复值。

    保持首次出现的顺序。

    Args:
        values: 值列表

    Returns:
        重复值列表

    Example:
        >>> duplicates = _duplicate_values(["a", "b", "a", "c", "b"])
        >>> duplicates
        ['a', 'b']
    """
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def validate_borehole(borehole: Borehole) -> list[str]:
    """校验单个钻孔的数据完整性。

    校验规则：
    1. 主文件必须有钻孔编号和孔深
    2. 孔深必须是有效数字
    3. 地层层底深度必须递增
    4. 每层必须有岩性代号
    5. 风化代码必须在有效范围内
    6. 最后层底深度应与孔深一致
    7. 基础文件深度应匹配 .-c 文件
    8. .-h 文件不应有重复深度
    9. 土钻孔不应有不支持的试验类型

    Args:
        borehole: 钻孔对象

    Returns:
        校验问题消息列表，为空表示校验通过

    Example:
        >>> messages = validate_borehole(borehole)
        >>> if not messages:
        ...     print("校验通过")
        ... else:
        ...     for msg in messages:
        ...         print(f"  - {msg}")
    """
    messages: list[str] = []
    lines = borehole.main.normalized_lines()

    # 校验主文件基本字段
    if not lines[0]:
        messages.append("主文件缺少钻孔编号。")
    if not lines[1]:
        messages.append("主文件缺少孔深。")

    # 校验孔深格式
    try:
        hole_depth = float(lines[1]) if lines[1] else None
    except ValueError:
        hole_depth = None
        messages.append(f"孔深不是有效数字：{lines[1]}")

    # 校验地层数据
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
        if layer.weathering and layer.weathering not in WEATHERING_MAP:
            messages.append(f"第 {index} 层风化代码无效：{layer.weathering}")

    # 校验孔深与层底深度一致性
    if hole_depth is not None and borehole.layers:
        try:
            last_depth = float(borehole.layers[-1].bottom_depth)
            if abs(last_depth - hole_depth) > 0.01:
                messages.append(f"最后层底深度 {last_depth:g} 与孔深 {hole_depth:g} 不一致。")
        except ValueError:
            pass

    # 校验基础文件深度匹配
    c_depths = {layer.bottom_depth for layer in borehole.layers if layer.bottom_depth}
    for suffix in ("b", "d", "g"):
        raw_text = borehole.raw_texts.get(f".-{suffix}")
        if not raw_text:
            continue
        extra_depths = [depth for depth in _pair_depths(raw_text) if depth not in c_depths]
        if extra_depths:
            messages.append(f".-{suffix} 存在未匹配 .-c 的深度：{', '.join(extra_depths)}")

    # 校验岩性描述文件
    h_raw_text = borehole.raw_texts.get(".-h")
    if h_raw_text:
        h_depths = _h_depths(h_raw_text)
        extra_h_depths = [depth for depth in h_depths if depth not in c_depths]
        if extra_h_depths:
            messages.append(f".-h 存在未匹配 .-c 的深度：{', '.join(extra_h_depths)}")
        duplicate_h_depths = _duplicate_values(h_depths)
        if duplicate_h_depths:
            messages.append(f".-h 存在重复深度：{', '.join(duplicate_h_depths)}")

    # 校验土钻孔试验类型
    if borehole.hole_type == "NZK":
        for suffix in ("e", "f", "m"):
            if borehole.tests.get(suffix):
                messages.append(f"NZK 土钻孔不应有 .-{suffix} 试验数据。")

    borehole.validation_messages = messages
    return messages


def validate_project(project: ProjectData) -> list[str]:
    """校验整个项目的数据完整性。

    对项目中的每个钻孔进行校验，并在消息前添加钻孔编号前缀。

    Args:
        project: 项目数据对象

    Returns:
        校验问题消息列表，为空表示校验通过

    Example:
        >>> messages = validate_project(project)
        >>> if not messages:
        ...     print("项目校验通过")
        ... else:
        ...     for msg in messages:
        ...         print(f"  - {msg}")
    """
    messages: list[str] = []
    for borehole in project.sorted_boreholes():
        for message in validate_borehole(borehole):
            messages.append(f"{borehole.prefix}: {message}")
    return messages
