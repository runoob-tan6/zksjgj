"""钻孔数据编辑工具 - 项目管理模块。

本模块负责项目级别的操作，包括：
- 项目加载和解析
- 钻孔创建和复制
- 钻孔编号管理
- 文件分组和识别

典型用法：
    >>> from borehole_app.project import load_project
    >>> project = load_project(Path("/data/project"))
    >>> print(f"加载了 {len(project.boreholes)} 个钻孔")
"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

from .models import Borehole, MainFileData, ProjectData
from .parser import parse_borehole

# ============================================================================
# 常量定义
# ============================================================================

KNOWN_SUFFIXES: set[str] = {"b", "c", "d", "e", "f", "g", "h", "l", "m", "n", "o", "q"}
"""已知的钻孔数据文件后缀集合。"""

BOREHOLE_PATTERN: re.Pattern = re.compile(r"^(?:NZK|ZK)[A-Z]*\d+(?:-\d+)?$", re.IGNORECASE)
"""钻孔编号正则表达式模式。"""

PROFILE_PATTERN: re.Pattern = re.compile(r"^[HZ]\d+$", re.IGNORECASE)
"""剖面编号正则表达式模式。"""


# ============================================================================
# 辅助函数
# ============================================================================


def is_borehole_prefix(prefix: str) -> bool:
    """判断是否为有效的钻孔编号前缀。

    有效的钻孔编号格式：ZK1、NZK1、ZKA1、ZK1-1 等。

    Args:
        prefix: 待判断的字符串

    Returns:
        是否为有效的钻孔编号前缀

    Example:
        >>> is_borehole_prefix("ZK1")
        True
        >>> is_borehole_prefix("NZK1")
        True
        >>> is_borehole_prefix("H1")
        False
    """
    return bool(BOREHOLE_PATTERN.fullmatch(prefix.strip()))


def is_profile_prefix(prefix: str) -> bool:
    """判断是否为有效的剖面编号前缀。

    有效的剖面编号格式：H1、Z1 等。

    Args:
        prefix: 待判断的字符串

    Returns:
        是否为有效的剖面编号前缀

    Example:
        >>> is_profile_prefix("H1")
        True
        >>> is_profile_prefix("ZK1")
        False
    """
    return bool(PROFILE_PATTERN.fullmatch(prefix.strip()))


def borehole_type_from_prefix(prefix: str) -> str:
    """从钻孔编号前缀判断钻孔类型。

    Args:
        prefix: 钻孔编号前缀

    Returns:
        钻孔类型，"ZK" 或 "NZK"

    Example:
        >>> borehole_type_from_prefix("ZK1")
        'ZK'
        >>> borehole_type_from_prefix("NZK1")
        'NZK'
    """
    return "NZK" if prefix.upper().startswith("NZK") else "ZK"


def split_borehole_file(path: Path) -> tuple[str | None, str | None]:
    """解析钻孔数据文件路径，提取编号前缀和后缀。

    Args:
        path: 文件路径

    Returns:
        (编号前缀, 后缀) 元组，无法解析时返回 (None, None)

    Example:
        >>> split_borehole_file(Path("ZK1.-c"))
        ('ZK1', 'c')
        >>> split_borehole_file(Path("ZK1"))
        ('ZK1', 'main')
        >>> split_borehole_file(Path("other.txt"))
        (None, None)
    """
    name = path.name
    if ".-" in name:
        prefix, suffix = name.split(".-", 1)
        if is_borehole_prefix(prefix) and suffix in KNOWN_SUFFIXES:
            return prefix, suffix
        return None, None
    if name.startswith("0") or path.suffix:
        return None, None
    if is_borehole_prefix(name):
        return name, "main"
    return None, None


# ============================================================================
# 项目操作
# ============================================================================


def create_empty_project() -> ProjectData:
    """创建空项目。

    Returns:
        空的 ProjectData 对象
    """
    return ProjectData()


def load_project(folder: Path) -> ProjectData:
    """加载项目，解析文件夹中的所有钻孔数据。

    Args:
        folder: 项目文件夹路径

    Returns:
        加载后的 ProjectData 对象

    Example:
        >>> project = load_project(Path("/data/project"))
        >>> if project.load_error:
        ...     print(f"加载失败：{project.load_error}")
        ... else:
        ...     print(f"加载了 {len(project.boreholes)} 个钻孔")
    """
    project = ProjectData(folder=folder)
    if not folder.exists() or not folder.is_dir():
        project.load_error = f"项目文件夹不存在：{folder}"
        return project

    groups: dict[str, dict[str, Path]] = {}
    for path in folder.iterdir():
        if not path.is_file():
            continue
        prefix, suffix = split_borehole_file(path)
        if not prefix or not suffix:
            continue
        groups.setdefault(prefix, {})[suffix] = path

    for prefix, files in groups.items():
        extra_files = {k: v for k, v in files.items() if k != "main"}
        project.boreholes[prefix] = parse_borehole(folder, prefix, extra_files)
    return project


def copy_borehole(project: ProjectData, source: Borehole, new_prefix: str) -> Borehole:
    """复制钻孔。

    Args:
        project: 项目数据对象
        source: 源钻孔对象
        new_prefix: 新钻孔编号

    Returns:
        复制后的钻孔对象

    Example:
        >>> new_borehole = copy_borehole(project, source, "ZK2")
        >>> new_borehole.is_new
        True
    """
    folder = project.folder or source.folder
    borehole = deepcopy(source)
    borehole.prefix = new_prefix
    borehole.folder = folder
    borehole.hole_type = borehole_type_from_prefix(new_prefix)
    borehole.is_new = True
    borehole.dirty = True
    borehole.dirty_suffixes = set()
    borehole.validation_messages = []
    borehole.raw_texts = {}
    borehole.existing_suffixes = set()
    lines = borehole.main.normalized_lines()
    lines[0] = new_prefix
    lines[12] = lines[1]
    borehole.main = MainFileData(lines=lines)
    project.boreholes[new_prefix] = borehole
    return borehole


def next_borehole_prefix(project: ProjectData, source_prefix: str) -> str:
    """生成下一个可用的钻孔编号。

    Args:
        project: 项目数据对象
        source_prefix: 源钻孔编号

    Returns:
        下一个可用的钻孔编号

    Example:
        >>> next_borehole_prefix(project, "ZK1")
        'ZK2'
        >>> next_borehole_prefix(project, "ZK1-1")
        'ZK1-2'
    """
    match = re.fullmatch(r"((?:NZK|ZK)[A-Z]*\d+)-(\d+)", source_prefix, re.IGNORECASE)
    if match:
        base = match.group(1)
        number = int(match.group(2)) + 1
        while f"{base}-{number}" in project.boreholes:
            number += 1
        return f"{base}-{number}"

    match = re.fullmatch(r"((?:NZK|ZK)[A-Z]*)(\d+)", source_prefix, re.IGNORECASE)
    if not match:
        return f"{source_prefix}-1"
    base = match.group(1)
    number = int(match.group(2)) + 1
    while f"{base}{number}" in project.boreholes:
        number += 1
    return f"{base}{number}"


def _find_template_borehole(project: ProjectData, hole_type: str) -> Borehole | None:
    """查找模板钻孔。

    优先查找同类型的已保存钻孔，其次是任意已保存钻孔。

    Args:
        project: 项目数据对象
        hole_type: 钻孔类型

    Returns:
        模板钻孔对象，无可用模板时返回None
    """
    same_type = [b for b in project.sorted_boreholes() if b.hole_type == hole_type and not b.is_new]
    if same_type:
        return same_type[0]
    existing = [b for b in project.sorted_boreholes() if not b.is_new]
    return existing[0] if existing else None


def _default_main_lines(prefix: str) -> list[str]:
    """生成默认的主文件内容。

    Args:
        prefix: 钻孔编号

    Returns:
        16行主文件内容列表
    """
    lines = [""] * 16
    lines[0] = prefix
    lines[4] = ",90"
    lines[8] = "001"
    lines[10] = "0,0"
    lines[13] = "L"
    lines[14] = ",90"
    return lines


def create_new_borehole(project: ProjectData, prefix: str) -> Borehole:
    """创建新钻孔。

    如果项目中有同类型钻孔，会使用模板创建；否则使用默认值。

    Args:
        project: 项目数据对象
        prefix: 新钻孔编号

    Returns:
        创建的钻孔对象

    Example:
        >>> borehole = create_new_borehole(project, "ZK1")
        >>> borehole.is_new
        True
    """
    folder = project.folder or Path.cwd()
    hole_type = borehole_type_from_prefix(prefix)
    template = _find_template_borehole(project, hole_type)
    if template:
        borehole = deepcopy(template)
        borehole.prefix = prefix
        borehole.folder = folder
        borehole.hole_type = hole_type
        borehole.is_new = True
        borehole.dirty = True
        borehole.validation_messages = []
        borehole.raw_texts = {}
        borehole.existing_suffixes = set()
        lines = borehole.main.normalized_lines()
        lines[0] = prefix
        lines[12] = lines[1]
        borehole.main = MainFileData(lines=lines)
    else:
        borehole = Borehole(prefix=prefix, folder=folder, hole_type=hole_type, is_new=True, dirty=True)
        borehole.main = MainFileData(lines=_default_main_lines(prefix))
    project.boreholes[prefix] = borehole
    return borehole
