"""钻孔数据编辑工具 - 文件解析模块。

本模块负责解析钻孔数据文件，包括：
- 主文件解析（固定16行格式）
- 配对文件解析（深度,值 格式）
- 岩性描述文件解析（#深度 + 描述格式）
- 试验数据文件解析
- 基础地层数据整合

支持的文件编码：UTF-8、GBK、ANSI。

典型用法：
    >>> from borehole_app.parser import parse_borehole
    >>> borehole = parse_borehole(Path("/data/ZK1"), "ZK1", files)
    >>> print(borehole.main.hole_id)
    'ZK1'
"""

from __future__ import annotations

from pathlib import Path

from .models import BasicLayer, Borehole, END_MARK, MainFileData, TestRecord


def read_text_file(path: Path) -> str:
    """读取文本文件，自动检测编码。

    按照 UTF-8 -> GBK -> ANSI 的顺序尝试解码，
    如果都失败则使用 UTF-8 替换模式读取。

    Args:
        path: 文件路径

    Returns:
        文件内容字符串

    Raises:
        FileNotFoundError: 文件不存在时

    Example:
        >>> content = read_text_file(Path("data.txt"))
        >>> print(content[:10])
        'ZK1\n10...'
    """
    for encoding in ("utf-8", "gbk", "ansi"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def clean_lines(text: str) -> list[str]:
    """清理文本行，移除行尾换行符。

    Args:
        text: 原始文本内容

    Returns:
        清理后的行列表

    Example:
        >>> lines = clean_lines("line1\nline2\r\n")
        >>> lines
        ['line1', 'line2']
    """
    return [line.rstrip("\r\n") for line in text.splitlines()]


def data_lines(path: Path) -> list[str]:
    """读取数据文件，返回有效数据行。

    移除空行和结束标记 ★。

    Args:
        path: 文件路径

    Returns:
        有效数据行列表，文件不存在时返回空列表

    Example:
        >>> lines = data_lines(Path("ZK1.-c"))
        >>> # 返回 ['5,A', '10,B', ...]
    """
    if not path.exists():
        return []
    lines = clean_lines(read_text_file(path))
    return [line for line in lines if line != END_MARK and line != ""]


def main_file_lines(path: Path) -> list[str]:
    """读取主文件，返回保留空行的内容行。

    与 data_lines 不同，此函数保留空行以维持16行结构。

    Args:
        path: 主文件路径

    Returns:
        主文件内容行列表（保留空行），文件不存在时返回空列表

    Example:
        >>> lines = main_file_lines(Path("ZK1"))
        >>> len(lines)
        16
    """
    if not path.exists():
        return []
    lines = clean_lines(read_text_file(path))
    return [line for line in lines if line != END_MARK]


def parse_main_file(path: Path) -> MainFileData:
    """解析主文件，返回 MainFileData 对象。

    主文件固定为16行，不足16行时用空字符串填充。

    Args:
        path: 主文件路径

    Returns:
        解析后的 MainFileData 对象

    Example:
        >>> data = parse_main_file(Path("ZK1"))
        >>> data.hole_id
        'ZK1'
        >>> data.depth
        '10.5'
    """
    lines = main_file_lines(path)
    while len(lines) < 16:
        lines.append("")
    return MainFileData(lines=lines[:16])


def parse_pair_file(path: Path) -> list[tuple[str, str]]:
    """解析配对文件（深度,值 格式）。

    文件格式：每行一个 "深度,值" 对，以逗号分隔。

    Args:
        path: 配对文件路径

    Returns:
        (深度, 值) 元组列表

    Example:
        >>> pairs = parse_pair_file(Path("ZK1.-c"))
        >>> pairs[0]
        ('5', 'A')
    """
    result: list[tuple[str, str]] = []
    for line in data_lines(path):
        parts = line.split(",", 1)
        if len(parts) == 2:
            result.append((parts[0].strip(), parts[1].strip()))
    return result


def parse_h_file(path: Path) -> dict[str, str]:
    """解析岩性描述文件（#深度 + 描述 格式）。

    文件格式：
        #深度1
        描述1
        #深度2
        描述2

    Args:
        path: 岩性描述文件路径

    Returns:
        深度到描述的映射字典

    Example:
        >>> descriptions = parse_h_file(Path("ZK1.-h"))
        >>> descriptions["5"]
        '强风化花岗岩'
    """
    result: dict[str, str] = {}
    lines = data_lines(path)
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if line.startswith("#"):
            depth = line[1:].strip()
            description = ""
            if index + 1 < len(lines):
                description = lines[index + 1].strip()
            result[depth] = description
            index += 2
        else:
            index += 1
    return result


def parse_test_file(path: Path) -> list[TestRecord]:
    """解析试验数据文件。

    文件格式：每行一个试验记录，值以逗号分隔。

    Args:
        path: 试验数据文件路径

    Returns:
        TestRecord 对象列表

    Example:
        >>> records = parse_test_file(Path("ZK1.-o"))
        >>> records[0].values
        ['1', '5', 'S1']
    """
    records: list[TestRecord] = []
    for line in data_lines(path):
        values = [part.strip() for part in line.split(",")]
        if values:
            records.append(TestRecord(values=values))
    return records


def parse_basic_layers(folder: Path, prefix: str) -> list[BasicLayer]:
    """解析基础地层数据，整合多个文件的信息。

    以 .-c 文件为主控，整合 .-b、.-d、.-g、.-h 文件的数据。
    如果没有 .-c 文件，则使用其他文件的深度并集。

    Args:
        folder: 钻孔数据文件夹路径
        prefix: 钻孔编号前缀

    Returns:
        BasicLayer 对象列表

    Example:
        >>> layers = parse_basic_layers(Path("/data"), "ZK1")
        >>> layers[0].bottom_depth
        '5'
        >>> layers[0].lithology_code
        'A'
    """
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


def _depth_key(value: str) -> tuple[int, float | str]:
    """深度排序键函数。

    数字深度按数值排序，非数字深度按字符串排序。
    数字深度排在非数字深度之前。

    Args:
        value: 深度值字符串

    Returns:
        排序键元组 (类型标识, 排序值)

    Example:
        >>> sorted(["abc", "10", "2"], key=_depth_key)
        ['2', '10', 'abc']
    """
    try:
        return (0, float(value))
    except ValueError:
        return (1, value)


def parse_borehole(folder: Path, prefix: str, files: dict[str, Path]) -> Borehole:
    """解析钻孔数据，返回完整的 Borehole 对象。

    整合主文件、基础数据文件和试验数据文件。

    Args:
        folder: 钻孔数据文件夹路径
        prefix: 钻孔编号前缀
        files: 文件后缀到路径的映射

    Returns:
        解析后的 Borehole 对象

    Example:
        >>> files = {"c": Path("ZK1.-c"), "b": Path("ZK1.-b")}
        >>> borehole = parse_borehole(Path("/data"), "ZK1", files)
        >>> borehole.hole_type
        'ZK'
        >>> len(borehole.layers)
        2
    """
    hole_type = "NZK" if prefix.upper().startswith("NZK") else "ZK"
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
