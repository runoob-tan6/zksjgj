import pytest

from borehole.infrastructure.xlsx_export import _to_float


@pytest.mark.parametrize("value", ["nan", "NaN", "inf", "-inf"])
def test_to_float_rejects_non_finite_values(value: str) -> None:
    assert _to_float(value) is None
