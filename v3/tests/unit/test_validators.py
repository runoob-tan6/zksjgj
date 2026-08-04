"""校验规则单元测试。"""

from __future__ import annotations

from pathlib import Path

from borehole.domain.enums import HoleType
from borehole.domain.models import BasicLayer, Borehole, MainFileData
from borehole.domain.models import TestRecord as Record
from borehole.domain.validators import validate_borehole


def _make_borehole(prefix="ZK1", depth="10", layers=None, hole_type=HoleType.ZK) -> Borehole:
    lines = [prefix, depth] + [""] * 14
    b = Borehole(prefix=prefix, folder=Path("/tmp"), hole_type=hole_type)
    b.main = MainFileData(lines=lines)
    if layers:
        b.layers = layers
    return b


class TestValidateBorehole:
    def test_valid_borehole(self):
        b = _make_borehole(layers=[
            BasicLayer(bottom_depth="5", lithology_code="A"),
            BasicLayer(bottom_depth="10", lithology_code="B"),
        ])
        msgs = validate_borehole(b)
        assert not msgs

    def test_missing_hole_id(self):
        b = _make_borehole(prefix="", depth="10")
        msgs = validate_borehole(b)
        assert any("编号" in m for m in msgs)

    def test_missing_depth(self):
        b = _make_borehole(depth="")
        msgs = validate_borehole(b)
        assert any("孔深" in m for m in msgs)

    def test_invalid_depth(self):
        b = _make_borehole(depth="abc")
        msgs = validate_borehole(b)
        assert any("有效数字" in m for m in msgs)

    def test_layer_not_ascending(self):
        b = _make_borehole(layers=[
            BasicLayer(bottom_depth="10", lithology_code="A"),
            BasicLayer(bottom_depth="5", lithology_code="B"),
        ])
        msgs = validate_borehole(b)
        assert any("递增" in m for m in msgs)

    def test_missing_lithology_code(self):
        b = _make_borehole(layers=[
            BasicLayer(bottom_depth="10", lithology_code=""),
        ])
        msgs = validate_borehole(b)
        assert any("岩性代号" in m for m in msgs)

    def test_invalid_weathering(self):
        b = _make_borehole(layers=[
            BasicLayer(bottom_depth="10", lithology_code="A", weathering="X"),
        ])
        msgs = validate_borehole(b)
        assert any("风化" in m for m in msgs)

    def test_depth_mismatch(self):
        b = _make_borehole(depth="10", layers=[
            BasicLayer(bottom_depth="8", lithology_code="A"),
        ])
        msgs = validate_borehole(b)
        assert any("不一致" in m for m in msgs)

    def test_nzk_forbidden_tests(self):
        b = _make_borehole(hole_type=HoleType.NZK)
        b.tests["e"] = [Record(values=["5", "80"])]
        msgs = validate_borehole(b)
        assert any("NZK" in m and "e" in m for m in msgs)

    def test_validation_does_not_mutate_borehole_messages(self):
        b = _make_borehole(depth="")
        b.validation_messages = ["existing"]

        msgs = validate_borehole(b)

        assert any("孔深" in message for message in msgs)
        assert b.validation_messages == ["existing"]
