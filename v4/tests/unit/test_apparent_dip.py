from __future__ import annotations

import math
import random

import pytest

from borehole.domain.apparent_dip import (
    AngleRange,
    DipSide,
    calculate_apparent_dip,
    normalize_azimuth,
)

NW = DipSide.COUNTERCLOCKWISE


def fixed(value: float) -> AngleRange:
    return AngleRange(value, value)


@pytest.mark.parametrize(
    ("section", "minimum", "maximum", "direction"),
    [
        (74, 3.258759348845604, 5.5375656750168645, "S74°W"),
        (344, 19.596574201005296, 24.72922036351813, "N16°W"),
    ],
)
def test_original_example(section, minimum, maximum, direction) -> None:
    result = calculate_apparent_dip(AngleRange(62, 65), NW, AngleRange(20, 25), section)
    assert result.minimum == pytest.approx(minimum)
    assert result.maximum == pytest.approx(maximum)
    assert result.direction == direction
    assert not result.warnings


@pytest.mark.parametrize("section", [62, 242])
def test_parallel_section_is_horizontal(section) -> None:
    result = calculate_apparent_dip(fixed(62), NW, fixed(25), section)
    assert result.minimum == result.maximum == 0
    assert result.direction == "水平，无视倾向"


@pytest.mark.parametrize("section", [152, 332])
def test_perpendicular_section_has_true_dip(section) -> None:
    result = calculate_apparent_dip(fixed(62), NW, fixed(25), section)
    assert result.minimum == pytest.approx(25)
    assert result.maximum == pytest.approx(25)
    assert result.direction == "N28°W"


def test_horizontal_layer_has_no_direction_even_for_broad_strike_range() -> None:
    result = calculate_apparent_dip(AngleRange(0, 180), NW, fixed(0), 74)
    assert result.minimum == result.maximum == 0
    assert result.direction == "水平，无视倾向"


def test_vertical_layer_parallel_to_strike_is_indeterminate() -> None:
    result = calculate_apparent_dip(fixed(62), NW, fixed(90), 242)
    assert result.minimum is result.maximum is None
    assert result.direction == "无法确定"
    assert "无法确定" in result.warnings[0]


def test_vertical_layer_nonparallel_is_vertical_without_unique_direction() -> None:
    result = calculate_apparent_dip(fixed(62), NW, fixed(90), 74)
    assert result.minimum == result.maximum == 90
    assert result.direction == "直立，无唯一视倾向"


def test_vertical_range_with_singular_combination_reports_valid_envelope_and_warning() -> None:
    result = calculate_apparent_dip(AngleRange(60, 80), NW, fixed(90), 74)
    assert result.minimum == result.maximum == 90
    assert "该组合无法确定" in result.warnings[0]
    assert all("可能为0" not in warning for warning in result.warnings)


def test_mixed_dip_range_with_parallel_strike_keeps_zero_and_reports_singularity() -> None:
    result = calculate_apparent_dip(fixed(62), NW, AngleRange(20, 90), 62)
    assert result.minimum == result.maximum == 0
    assert result.direction == "水平，无视倾向"
    assert result.warnings


def test_range_checks_interior_maximum_and_minimum() -> None:
    maximum = calculate_apparent_dip(AngleRange(45, 135), NW, fixed(20), 0)
    assert maximum.minimum == pytest.approx(14.432755043267381)
    assert maximum.maximum == pytest.approx(20)
    minimum = calculate_apparent_dip(AngleRange(60, 80), NW, AngleRange(20, 25), 74)
    assert minimum.minimum == 0
    assert minimum.maximum == pytest.approx(6.436327674423229)
    assert "反转" in minimum.direction
    assert "N74°E" in minimum.direction and "S74°W" in minimum.direction


def test_range_touching_parallel_position_does_not_claim_direction_reversal() -> None:
    result = calculate_apparent_dip(AngleRange(62, 74), NW, fixed(20), 74)
    assert result.minimum == 0
    assert result.direction == "S74°W"


def test_north_crossing_uses_continuous_unwrapped_interval() -> None:
    result = calculate_apparent_dip(AngleRange(350, 370), NW, AngleRange(20, 25), 0)
    assert result.minimum == 0
    assert result.maximum == pytest.approx(4.629338270886691)
    assert "反转" in result.direction


def test_half_circle_range_includes_reversal_when_endpoints_are_parallel() -> None:
    result = calculate_apparent_dip(AngleRange(0, 180), NW, fixed(20), 90)
    assert result.minimum == 0
    assert result.maximum == pytest.approx(20)
    assert "反转" in result.direction


def test_reversing_section_preserves_physical_direction() -> None:
    a = calculate_apparent_dip(fixed(63.5), NW, fixed(22.5), 74)
    b = calculate_apparent_dip(fixed(63.5), NW, fixed(22.5), 254)
    assert a.minimum == pytest.approx(b.minimum)
    assert a.direction == b.direction


def test_switching_dip_side_reverses_direction_without_changing_angle() -> None:
    a = calculate_apparent_dip(fixed(63.5), NW, fixed(22.5), 74)
    b = calculate_apparent_dip(fixed(63.5), DipSide.CLOCKWISE, fixed(22.5), 74)
    assert a.minimum == b.minimum
    assert a.direction == "S74°W"
    assert b.direction == "N74°E"


def test_tiny_nonzero_angles_are_preserved_near_vertical() -> None:
    result = calculate_apparent_dip(fixed(0), NW, fixed(89.999999), 1e-12)
    assert result.minimum == pytest.approx(0.00005729578, abs=1e-10)
    assert result.direction.startswith("S") and result.direction.endswith("°W")
    small_dip = calculate_apparent_dip(fixed(0), NW, fixed(1e-10), 90)
    assert small_dip.minimum == pytest.approx(1e-10, abs=1e-15)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_ranges_are_rejected(value) -> None:
    with pytest.raises(ValueError, match="有限"):
        AngleRange(value, value)


@pytest.mark.parametrize("value", [-1, 361, math.nan, math.inf])
def test_invalid_section_azimuth_is_rejected(value) -> None:
    with pytest.raises(ValueError):
        calculate_apparent_dip(fixed(62), NW, fixed(20), value)


@pytest.mark.parametrize("dip", [AngleRange(-1, 20), AngleRange(20, 91)])
def test_invalid_dip_is_rejected(dip) -> None:
    with pytest.raises(ValueError, match="倾角"):
        calculate_apparent_dip(fixed(62), NW, dip, 74)


def test_reversed_or_oversize_ranges_are_rejected() -> None:
    with pytest.raises(ValueError, match="下限"):
        AngleRange(65, 62)
    with pytest.raises(ValueError, match="180"):
        calculate_apparent_dip(AngleRange(0, 181), NW, fixed(20), 74)
    assert normalize_azimuth(360) == 0


def _intersection_angle(dip: float, strike: float, section: float) -> float:
    """Independent cross product of a bedding plane and a vertical section."""
    alpha, direction, azimuth = map(math.radians, (dip, strike - 90, section))
    nx = math.sin(alpha) * math.sin(direction)
    ny = math.sin(alpha) * math.cos(direction)
    nz = math.cos(alpha)
    sx, sy = math.cos(azimuth), -math.sin(azimuth)
    x, y, z = -nz * sy, nz * sx, nx * sy - ny * sx
    return math.degrees(math.atan2(abs(z), math.hypot(x, y)))


def test_randomized_single_values_match_independent_plane_intersections() -> None:
    rng = random.Random(20261014)
    for _ in range(3000):
        strike, section = rng.uniform(0, 360), rng.uniform(0, 360)
        dip = rng.uniform(0, 89.999)
        result = calculate_apparent_dip(fixed(strike), NW, fixed(dip), section)
        assert result.minimum == pytest.approx(_intersection_angle(dip, strike, section), abs=1e-9)
        assert result.is_single_value


def test_randomized_range_envelopes_contain_independent_samples() -> None:
    rng = random.Random(20261014)
    for _ in range(200):
        start = rng.uniform(-90, 360)
        end = start + rng.uniform(0, 180)
        low = rng.uniform(0, 70)
        high = rng.uniform(low, 89.99)
        section = rng.uniform(0, 360)
        result = calculate_apparent_dip(AngleRange(start, end), NW, AngleRange(low, high), section)
        assert result.minimum is not None and result.maximum is not None
        for i in range(21):
            for j in range(5):
                value = _intersection_angle(
                    low + (high - low) * j / 4, start + (end - start) * i / 20, section
                )
                assert result.minimum - 1e-9 <= value <= result.maximum + 1e-9
