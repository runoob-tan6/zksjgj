"""钻孔数据编辑工具 - 文件写入模块。

本模块负责将钻孔数据写入文件，包括：
- 主文件生成
- 配对文件生成（深度,值 格式）
- 岩性描述文件生成（#深度 + 描述 格式）
- 试验数据文件生成
- 文件备份机制
- 地层试验导出

写入时保留原文件编码（UTF-8或GBK），新文件默认使用UTF-8。

典型用法：
    >>> from borehole_app.writer import generate_borehole
    >>> generated_files = generate_borehole(borehole)
    >>> print(f"生成了 {len(generated_files)} 个文件")
"""

from __future__ import annotations

import csv
import shutil
from datetime import datetime
from pathlib import Path

from .models import Borehole, END_MARK, ProjectData

# ============================================================================
# 常量定义
# ============================================================================

LAYER_TEST_TYPES: dict[str, str] = {
    "o": "取样",
    "q": "标贯",
    "n": "注水",
    "m": "压水",
}
"""地层试验类型映射。"""

LAYER_TEST_VALUE_NAMES: dict[str, str] = {
    "o": "样品编号",
    "q": "标贯击数",
    "n": "渗透系数",
    "m": "透水率",
}
"""地层试验结果字段名称映射。"""

LAYER_TEST_EXPORT_HEADERS: list[str] = [
    "钻孔编号",
    "层序号",
    "地层时代/成因",
    "岩性代号",
    "试验类型",
    "数量",
    "试验起始深度",
    "试验终止深度",
    "结果值/编号",
    "结果字段",
]
"""地层试验导出CSV表头。"""


# ============================================================================
# 基础文件操作
# ============================================================================


def make_file_text(lines: Iterable[str]) -> str:
    """生成文件文本内容，在末尾添加结束标记。

    Args:
        lines: 内容行迭代器

    Returns:
        包含结束标记的完整文件文本

    Example:
        >>> text = make_file_text(["line1", "line2"])
        >>> text
        'line1\\nline2\\n★'
    """
    clean = [str(line) for line in lines]
    return "\n".join(clean + [END_MARK])


def read_existing_text(path: Path) -> str | None:
    """读取现有文件文本内容。

    Args:
        path: 文件路径

    Returns:
        文件内容字符串，文件不存在时返回None
    """
    text, _encoding = read_existing_text_with_encoding(path)
    return text


def read_existing_text_with_encoding(path: Path) -> tuple[str | None, str]:
    """读取现有文件文本内容及编码。

    按照 UTF-8 -> GBK 的顺序尝试解码。

    Args:
        path: 文件路径

    Returns:
        (文件内容, 编码) 元组，文件不存在时返回 (None, "utf-8")
    """
    if not path.exists():
        return None, "utf-8"
    for encoding in ("utf-8", "gbk"):
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace"), "utf-8"


def normalize_for_compare(text: str | None) -> str | None:
    """标准化文本用于比较。

    统一换行符为 \\n，并移除末尾换行。

    Args:
        text: 原始文本

    Returns:
        标准化后的文本，None输入返回None
    """
    if text is None:
        return None
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def backup_existing_file(path: Path, backup_folder: Path | None = None) -> Path | None:
    """备份现有文件。

    使用 shutil.copy2 保留原文件编码和元数据。
    备份文件名格式：原文件名.时间戳.bak

    Args:
        path: 要备份的文件路径
        backup_folder: 备份文件夹路径，为None时使用原文件所在目录

    Returns:
        备份文件路径，原文件不存在时返回None
    """
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_dir = backup_folder or path.parent
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{path.name}.{timestamp}.bak"
    shutil.copy2(path, backup)
    return backup


def write_with_backup(path: Path, text: str, backup_folder: Path | None = None) -> bool:
    """写入文件，内容变化时自动备份。

    保留原文件编码（UTF-8或GBK），新文件使用UTF-8。

    Args:
        path: 目标文件路径
        text: 要写入的文本内容
        backup_folder: 备份文件夹路径

    Returns:
        是否实际写入了文件（内容无变化时返回False）
    """
    existing_text, encoding = read_existing_text_with_encoding(path)
    existing = normalize_for_compare(existing_text)
    current = normalize_for_compare(text)
    if existing == current:
        return False
    backup_existing_file(path, backup_folder)
    path.write_text(text, encoding=encoding)
    return True


# ============================================================================
# 文件内容渲染
# ============================================================================


def render_main_file(borehole: Borehole) -> str:
    """渲染主文件内容。

    套管下入深度（第13行）始终等于孔深（第2行）。

    Args:
        borehole: 钻孔对象

    Returns:
        主文件文本内容
    """
    lines = borehole.main.normalized_lines()
    lines[12] = lines[1]  # 套管下入深度始终等于孔深
    return make_file_text(lines)


def render_pair_file(rows: list[tuple[str, str]], skip_empty_value: bool = False) -> str:
    """渲染配对文件内容（深度,值 格式）。

    Args:
        rows: (深度, 值) 元组列表
        skip_empty_value: 是否跳过值为空的行

    Returns:
        配对文件文本内容
    """
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
    """渲染岩性描述文件内容（#深度 + 描述 格式）。

    Args:
        borehole: 钻孔对象

    Returns:
        岩性描述文件文本内容
    """
    lines: list[str] = []
    for layer in borehole.layers:
        if layer.bottom_depth or layer.description:
            lines.append(f"#{layer.bottom_depth}")
            lines.append(layer.description)
    return make_file_text(lines)


def test_file_lines(borehole: Borehole, suffix: str) -> list[str]:
    """生成试验文件内容行。

    Args:
        borehole: 钻孔对象
        suffix: 试验数据后缀

    Returns:
        试验文件内容行列表
    """
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
    """渲染试验文件内容。

    Args:
        borehole: 钻孔对象
        suffix: 试验数据后缀

    Returns:
        试验文件文本内容
    """
    return make_file_text(test_file_lines(borehole, suffix))


# ============================================================================
# 钻孔文件生成
# ============================================================================


def generate_borehole(borehole: Borehole, old_prefix: str | None = None) -> list[Path]:
    """生成钻孔数据文件。

    根据钻孔状态决定生成策略：
    - 新增/复制/编号变更：保存所有文件
    - 普通修改：只保存 dirty_suffixes 记录的文件

    Args:
        borehole: 钻孔对象
        old_prefix: 编号变更前的旧前缀

    Returns:
        实际生成/修改的文件路径列表
    """
    generated: list[Path] = []
    folder = borehole.folder
    folder.mkdir(parents=True, exist_ok=True)

    # 新增、复制或编号变更时，需要保存完整钻孔；普通修改只保存 dirty_suffixes 记录的文件类型
    full_save = borehole.is_new or bool(old_prefix and old_prefix != borehole.prefix)
    old_paths_to_remove: list[Path] = []
    if old_prefix and old_prefix != borehole.prefix:
        for suffix in borehole.existing_suffixes:
            old_path = folder / (f"{old_prefix}.-{suffix}" if suffix != "main" else old_prefix)
            if old_path.exists():
                old_paths_to_remove.append(old_path)

    all_targets = {
        "main": (folder / borehole.prefix, render_main_file(borehole)),
        "c": (folder / f"{borehole.prefix}.-c", render_pair_file([(l.bottom_depth, l.lithology_code) for l in borehole.layers])),
        "b": (folder / f"{borehole.prefix}.-b", render_pair_file([(l.bottom_depth, l.formation) for l in borehole.layers], skip_empty_value=True)),
        "d": (folder / f"{borehole.prefix}.-d", render_pair_file([(l.bottom_depth, l.structure) for l in borehole.layers], skip_empty_value=True)),
        "g": (folder / f"{borehole.prefix}.-g", render_pair_file([(l.bottom_depth, l.weathering) for l in borehole.layers], skip_empty_value=True)),
        "h": (folder / f"{borehole.prefix}.-h", render_h_file(borehole)),
    }

    for suffix in borehole.available_test_suffixes():
        lines = test_file_lines(borehole, suffix)
        should_write_empty_existing = suffix in borehole.dirty_suffixes and suffix in borehole.existing_suffixes
        if lines or should_write_empty_existing:
            all_targets[suffix] = (folder / f"{borehole.prefix}.-{suffix}", make_file_text(lines))

    suffixes_to_save = set(all_targets) if full_save or not borehole.dirty_suffixes else set(borehole.dirty_suffixes)
    for suffix in suffixes_to_save:
        target = all_targets.get(suffix)
        if not target:
            continue
        path, text = target
        if write_with_backup(path, text, folder / "tmp"):
            generated.append(path)

    for old_path in old_paths_to_remove:
        if old_path.exists():
            backup_existing_file(old_path, folder / "tmp")
            old_path.unlink()

    borehole.dirty = False
    borehole.is_new = False
    borehole.dirty_suffixes.clear()
    return generated


# ============================================================================
# 地层试验导出
# ============================================================================


def _to_float(value: str) -> float | None:
    """安全转换字符串为浮点数。

    Args:
        value: 字符串值

    Returns:
        浮点数，转换失败时返回None
    """
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _fmt_depth(value: float) -> str:
    """格式化深度值。

    Args:
        value: 深度值

    Returns:
        格式化后的深度字符串
    """
    return f"{value:g}"


def _fmt_test_result(suffix: str, value: str) -> str:
    """格式化试验结果值。

    注水试验（n）使用科学记数法。

    Args:
        suffix: 试验类型后缀
        value: 结果值

    Returns:
        格式化后的结果字符串
    """
    if suffix != "n":
        return value
    number = _to_float(value)
    if number is None:
        return value
    return f"{number:.2E}"


def _layer_ranges(borehole: Borehole):
    """生成地层深度范围。

    Args:
        borehole: 钻孔对象

    Yields:
        (层序号, 层顶深度, 层底深度, 地层) 元组
    """
    top = 0.0
    for index, layer in enumerate(borehole.layers, start=1):
        bottom = _to_float(layer.bottom_depth)
        if bottom is None or bottom <= top:
            continue
        yield index, top, bottom, layer
        top = bottom


def _test_matches_layer(suffix: str, test_top: float, test_bottom: float, layer_top: float, layer_bottom: float) -> bool:
    """判断试验是否属于指定地层。

    压水试验（m）使用区间重叠判断，其他试验使用起始深度判断。

    Args:
        suffix: 试验类型后缀
        test_top: 试验起始深度
        test_bottom: 试验终止深度
        layer_top: 地层顶深度
        layer_bottom: 地层底深度

    Returns:
        是否匹配
    """
    if suffix == "m":
        return test_top < layer_bottom and test_bottom > layer_top
    return layer_top <= test_top < layer_bottom


def _layer_test_sort_key(suffix: str, borehole: Borehole, record_index: int, layer_index: int, layer) -> tuple:
    """生成地层试验排序键。

    Args:
        suffix: 试验类型后缀
        borehole: 钻孔对象
        record_index: 记录索引
        layer_index: 地层索引
        layer: 地层对象

    Returns:
        排序键元组
    """
    type_index = list(LAYER_TEST_TYPES).index(suffix)
    if suffix == "m":
        return (type_index, borehole.prefix, record_index, layer_index, layer.formation, layer.lithology_code)
    return (type_index, layer.formation, layer.lithology_code, layer_index, borehole.prefix, record_index)


def _layer_test_data_row(
    suffix: str,
    borehole: Borehole,
    layer_index: int,
    layer,
    test_type: str,
    test_top: float,
    test_bottom: float,
    result_value: str,
) -> list:
    """生成地层试验数据行。

    Args:
        suffix: 试验类型后缀
        borehole: 钻孔对象
        layer_index: 地层索引
        layer: 地层对象
        test_type: 试验类型名称
        test_top: 试验起始深度
        test_bottom: 试验终止深度
        result_value: 结果值

    Returns:
        数据行列表
    """
    return [
        borehole.prefix,
        layer_index,
        layer.formation,
        layer.lithology_code,
        test_type,
        1,
        _fmt_depth(test_top),
        _fmt_depth(test_bottom),
        _fmt_test_result(suffix, result_value),
        LAYER_TEST_VALUE_NAMES[suffix],
    ]


def _layer_test_rows(project: ProjectData) -> list[tuple]:
    """生成地层试验数据行列表。

    Args:
        project: 项目数据对象

    Returns:
        数据行元组列表
    """
    rows = []
    for borehole in project.sorted_boreholes():
        ranges = list(_layer_ranges(borehole))
        if not ranges:
            continue
        for suffix, test_type in LAYER_TEST_TYPES.items():
            for record_index, record in enumerate(borehole.tests.get(suffix, [])):
                values = [str(value).strip() for value in record.values]
                while len(values) < 3:
                    values.append("")
                test_top = _to_float(values[0])
                test_bottom = _to_float(values[1])
                if test_top is None or test_bottom is None or test_bottom <= test_top:
                    continue
                result_value = values[2]
                for layer_index, layer_top, layer_bottom, layer in ranges:
                    if not _test_matches_layer(suffix, test_top, test_bottom, layer_top, layer_bottom):
                        continue
                    sort_key = _layer_test_sort_key(suffix, borehole, record_index, layer_index, layer)
                    data_row = _layer_test_data_row(suffix, borehole, layer_index, layer, test_type, test_top, test_bottom, result_value)
                    rows.append((*sort_key, data_row))
                    if suffix != "m":
                        break
    return rows


def export_layer_test_summary(project: ProjectData, target_path: Path) -> int:
    """导出地层试验汇总表。

    生成CSV文件，包含所有钻孔的地层试验数据。

    Args:
        project: 项目数据对象
        target_path: 目标文件路径

    Returns:
        导出的数据行数

    Example:
        >>> count = export_layer_test_summary(project, Path("export.csv"))
        >>> print(f"导出了 {count} 行数据")
    """
    rows = _layer_test_rows(project)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(LAYER_TEST_EXPORT_HEADERS)
        writer.writerows(row for *_sort, row in sorted(rows, key=lambda item: item[:-1]))
    return len(rows)


def delete_borehole_files(borehole: Borehole) -> list[Path]:
    """删除钻孔数据文件。

    删除前会备份文件。

    Args:
        borehole: 钻孔对象

    Returns:
        已删除的文件路径列表
    """
    deleted: list[Path] = []
    suffixes = set(borehole.existing_suffixes)
    if not suffixes:
        suffixes = {"main"}
    for suffix in suffixes:
        path = borehole.folder / (f"{borehole.prefix}.-{suffix}" if suffix != "main" else borehole.prefix)
        if path.exists():
            backup_existing_file(path, borehole.folder / "tmp")
            path.unlink()
            deleted.append(path)
    return deleted


def generate_dirty_boreholes(project: ProjectData) -> list[Path]:
    """生成所有有修改的钻孔数据文件。

    先删除已删除的钻孔文件，再生成有修改的钻孔文件。

    Args:
        project: 项目数据对象

    Returns:
        生成/删除的文件路径列表
    """
    generated: list[Path] = []
    for borehole in list(project.deleted_boreholes.values()):
        generated.extend(delete_borehole_files(borehole))
    project.deleted_boreholes.clear()
    for borehole in project.dirty_boreholes():
        generated.extend(generate_borehole(borehole, old_prefix=borehole.old_prefix))
        borehole.old_prefix = None
    return generated
