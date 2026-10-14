"""视倾角计算领域逻辑。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class DipSide(str, Enum):
    """相对于走向的倾向侧。"""

    CLOCKWISE = "顺时针侧"
    COUNTERCLOCKWISE = "逆时针侧"


@dataclass(frozen=True)
class AngleRange:
    """角度范围，单位为度。"""

    start: float
    end: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.start) or not math.isfinite(self.end):
            raise ValueError("角度必须是有限数值")
        if self.start > self.end:
            raise ValueError("范围下限不能大于上限")


@dataclass(frozen=True)
class ApparentDipResult:
    """一个剖面方向的视倾角结果。"""

    minimum: float | None
    maximum: float | None
    direction: str
    warnings: tuple[str, ...] = ()

    @property
    def is_single_value(self) -> bool:
        return (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum == self.maximum
        )


def normalize_azimuth(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("方位角必须是有限数值")
    if not 0 <= value <= 360:
        raise ValueError("方位角必须在0°到360°之间")
    return value % 360


def validate_dip_range(dip: AngleRange) -> None:
    if dip.start < 0 or dip.end > 90:
        raise ValueError("倾角必须在0°到90°之间")


def _q_values(strike: AngleRange, section: float) -> list[float]:
    """取得 |sin(剖面-走向)| 的端点和内部极值。"""
    def magnitude(value: float) -> float:
        difference = (section - value) % 180
        return 0.0 if difference == 0 else abs(math.sin(math.radians(difference)))

    values = [magnitude(strike.start), magnitude(strike.end)]
    first = math.ceil((strike.start - section - 90) / 180)
    last = math.floor((strike.end - section - 90) / 180)
    for index in range(first, last + 1):
        candidate = section + 90 + index * 180
        if strike.start <= candidate <= strike.end:
            values.append(1.0)
    first = math.ceil((strike.start - section) / 180)
    last = math.floor((strike.end - section) / 180)
    for index in range(first, last + 1):
        candidate = section + index * 180
        if strike.start <= candidate <= strike.end:
            values.append(0.0)
    return values


def _apparent_dip(dip: float, q: float) -> float | None:
    horizontal = 0.0 if dip == 90 else math.cos(math.radians(dip))
    vertical = math.sin(math.radians(dip)) * q
    if horizontal == 0 and vertical == 0:
        return None
    return math.degrees(math.atan2(vertical, horizontal))


def _bearing_text(value: float) -> str:
    value %= 360
    if value == 0:
        return "N"
    if value == 90:
        return "E"
    if value == 180:
        return "S"
    if value == 270:
        return "W"
    if value < 90:
        return f"N{value:g}°E"
    if value < 180:
        return f"S{180 - value:g}°E"
    if value < 270:
        return f"S{value - 180:g}°W"
    return f"N{360 - value:g}°W"


def _direction_candidates(
    strike: AngleRange, section: float, side: DipSide
) -> set[int]:
    """沿剖面正向的下倾符号，检查跨过走向时的反转。"""
    offset = 90 if side is DipSide.CLOCKWISE else -90
    strikes = [strike.start, strike.end]
    first = math.ceil((strike.start - section) / 180)
    last = math.floor((strike.end - section) / 180)
    for index in range(first, last + 1):
        candidate = section + index * 180
        if strike.start <= candidate <= strike.end:
            strikes.append(candidate)
    strikes = sorted(set(strikes))
    intervals = tuple(strikes)
    strikes.extend((a + b) / 2 for a, b in zip(intervals, intervals[1:]))
    signs: set[int] = set()
    for value in strikes:
        difference = (section - value) % 360
        if difference % 180 != 0:
            dot = math.sin(math.radians(difference)) * (1 if offset == 90 else -1)
            signs.add(1 if dot > 0 else -1)
    return signs


def calculate_apparent_dip(
    strike: AngleRange,
    side: DipSide,
    dip: AngleRange,
    section_azimuth: float,
) -> ApparentDipResult:
    """计算给定剖面方向的视倾角范围。"""
    if strike.end - strike.start > 180:
        raise ValueError("走向范围跨度不能超过180°")
    if not isinstance(side, DipSide):
        raise ValueError("请选择有效倾向侧")
    validate_dip_range(dip)
    section = normalize_azimuth(section_azimuth)
    q_values = _q_values(strike, section)
    q_min, q_max = min(q_values), max(q_values)
    values = [
        _apparent_dip(angle, q)
        for angle in (dip.start, dip.end)
        for q in (q_min, q_max)
    ]
    valid = [value for value in values if value is not None]
    warnings: list[str] = []
    if not valid:
        warnings.append("直立层且剖面平行走向，无法确定该剖面内的视倾角。")
        return ApparentDipResult(None, None, "无法确定", tuple(warnings))
    if dip.end == 90 and q_min == 0:
        warnings.append("输入范围包含直立层与剖面平行走向的组合，该组合无法确定视倾角。")
    signs = _direction_candidates(strike, section, side)
    if dip.end == 0:
        direction = "水平，无视倾向"
    elif dip.start == 90:
        direction = "直立，无唯一视倾向"
    elif len(signs) > 1:
        direction = f"{_bearing_text(section)} / {_bearing_text(section + 180)}（范围内反转）"
        warnings.append("走向范围跨过剖面方向，视倾向在范围内反转。")
    elif not signs:
        direction = "水平，无视倾向"
    else:
        direction = _bearing_text(section if 1 in signs else section + 180)
    if dip.start == 0 < dip.end:
        warnings.append("倾角范围包含水平层，0°时无视倾向。")
    if dip.start < 90 == dip.end and q_max > 0:
        warnings.append("倾角范围包含直立层，90°时无唯一视倾向。")
    return ApparentDipResult(min(valid), max(valid), direction, tuple(warnings))
