"""标贯杆长修正 + 分层统计参数计算。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from ..domain.models import Borehole


def correction_coefficient(rod_length: float) -> float | None:
    """根据杆长返回修正系数 α。返回 None 表示杆长 > 21，需手动处理。"""
    if rod_length <= 3:
        return 1.00
    elif rod_length <= 6:
        return 0.92
    elif rod_length <= 9:
        return 0.86
    elif rod_length <= 12:
        return 0.81
    elif rod_length <= 15:
        return 0.77
    elif rod_length <= 18:
        return 0.73
    elif rod_length <= 21:
        return 0.70
    else:
        return None


@dataclass
class CorrectedSPT:
    """单条修正后的标贯记录。"""
    start_depth: str
    end_depth: str
    rod_length: float
    raw_n: float
    alpha: float | None
    corrected_n: float | None
    warning: str = ""


@dataclass
class LayerStats:
    """单层统计结果。"""
    layer_name: str
    layer_index: int
    values: list[float] = field(default_factory=list)
    count: int = 0
    min_val: float = 0.0
    max_val: float = 0.0
    mean: float = 0.0
    std_dev: float = 0.0
    cov: float = 0.0
    gamma_s: float = 0.0
    standard_value: float = 0.0
    warnings: list[str] = field(default_factory=list)
    has_standard_value: bool = True


def correct_spt_records(borehole: Borehole) -> list[CorrectedSPT]:
    """对单个钻孔的标贯记录进行杆长修正。杆长取起始深度。"""
    records = borehole.tests.get("q", [])
    results: list[CorrectedSPT] = []
    for record in records:
        values = list(record.values)
        while len(values) < 3:
            values.append("")
        start_depth_str = values[0].strip()
        end_depth_str = values[1].strip()
        raw_n_str = values[2].strip()

        try:
            rod_length = float(start_depth_str)
        except (ValueError, TypeError):
            rod_length = 0.0

        try:
            raw_n = float(raw_n_str)
        except (ValueError, TypeError):
            raw_n = 0.0

        alpha = correction_coefficient(rod_length)
        warning = ""
        if alpha is None:
            warning = f"杆长 {rod_length:.1f}m > 21m，需手动处理"
            corrected_n = None
        else:
            corrected_n = round(alpha * raw_n, 2)

        results.append(CorrectedSPT(
            start_depth=start_depth_str,
            end_depth=end_depth_str,
            rod_length=rod_length,
            raw_n=raw_n,
            alpha=alpha,
            corrected_n=corrected_n,
            warning=warning,
        ))
    return results


def _find_layer_for_depth(borehole: Borehole, depth: float) -> tuple[int, str]:
    """根据深度找到所属地层。返回 (层序号, 岩性代号)。"""
    for i, layer in enumerate(borehole.layers, start=1):
        try:
            layer_depth = float(layer.bottom_depth)
        except (ValueError, TypeError):
            continue
        if depth < layer_depth:
            return i, layer.lithology_code
    if borehole.layers:
        return len(borehole.layers), borehole.layers[-1].lithology_code
    return 0, ""


def compute_layer_stats(project) -> list[LayerStats]:
    """按地层分组计算全项目标贯统计参数。"""
    groups: dict[str, list[float]] = {}

    for borehole in project.sorted_boreholes():
        corrected = correct_spt_records(borehole)
        for rec in corrected:
            if rec.corrected_n is None:
                continue
            try:
                depth = float(rec.start_depth)
            except (ValueError, TypeError):
                continue
            _, layer_code = _find_layer_for_depth(borehole, depth)
            key = layer_code or "未知"
            groups.setdefault(key, []).append(rec.corrected_n)

    results: list[LayerStats] = []
    for layer_code, values in sorted(groups.items()):
        stats = LayerStats(
            layer_name=layer_code,
            layer_index=0,
            values=values,
        )
        n = len(values)
        stats.count = n

        if n == 0:
            results.append(stats)
            continue

        stats.min_val = min(values)
        stats.max_val = max(values)
        stats.mean = sum(values) / n

        warnings = []
        if n < 3:
            stats.has_standard_value = False
            warnings.append("样本不足，无法计算标准值")
        elif n < 6:
            warnings.append("样本数不足，统计结果仅供参考")
            variance = sum((x - stats.mean) ** 2 for x in values) / (n - 1)
            stats.std_dev = math.sqrt(variance)
            stats.cov = stats.std_dev / stats.mean if stats.mean != 0 else 0
            stats.gamma_s = 1 - (1.704 / math.sqrt(n) + 4.678 / (n ** 2)) * stats.cov
            stats.standard_value = round(stats.gamma_s * stats.mean, 2)
        else:
            variance = sum((x - stats.mean) ** 2 for x in values) / (n - 1)
            stats.std_dev = math.sqrt(variance)
            stats.cov = stats.std_dev / stats.mean if stats.mean != 0 else 0
            if stats.cov > 0.3:
                warnings.append("变异性较高，建议检查异常数据")
            stats.gamma_s = 1 - (1.704 / math.sqrt(n) + 4.678 / (n ** 2)) * stats.cov
            stats.standard_value = round(stats.gamma_s * stats.mean, 2)

        stats.mean = round(stats.mean, 2)
        stats.std_dev = round(stats.std_dev, 2)
        stats.cov = round(stats.cov, 3)
        stats.gamma_s = round(stats.gamma_s, 3)
        stats.warnings = warnings
        results.append(stats)

    return results
