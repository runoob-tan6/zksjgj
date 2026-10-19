"""领域模型单元测试。"""

from __future__ import annotations

from pathlib import Path

from borehole.domain.enums import WEATHERING_LABELS, HoleType, Weathering
from borehole.domain.models import (
    BasicLayer,
    Borehole,
    MainFileData,
    ProjectData,
)


class TestMainFileData:
    def test_default_lines_are_16(self):
        data = MainFileData()
        lines = data.normalized_lines()
        assert len(lines) == 16

    def test_hole_id_property(self):
        data = MainFileData(lines=["ZK1", "10.5"])
        assert data.hole_id == "ZK1"
        assert data.depth == "10.5"

    def test_hole_id_setter(self):
        data = MainFileData(lines=["ZK1"] + [""] * 15)
        data.hole_id = "ZK2"
        assert data.lines[0] == "ZK2"

    def test_set_depth_updates_hole_and_casing_depth(self):
        data = MainFileData(lines=["ZK1", "10"] + [""] * 14)

        data.set_depth("12.5")

        assert data.depth == "12.5"
        assert data.normalized_lines()[12] == "12.5"

    def test_fixed_defaults_filled(self):
        data = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        lines = data.normalized_lines()
        assert lines[4] == ",90"
        assert lines[8] == "001"
        assert lines[13] == "L"


class TestBasicLayer:
    def test_defaults(self):
        layer = BasicLayer()
        assert layer.bottom_depth == ""
        assert layer.lithology_code == ""

    def test_with_values(self):
        layer = BasicLayer(bottom_depth="5", lithology_code="A", formation="Q")
        assert layer.bottom_depth == "5"


class TestBorehole:
    def test_display_name_new(self):
        b = Borehole(prefix="ZK1", folder=Path("/tmp"), hole_type=HoleType.ZK, is_new=True)
        assert b.display_name() == "*ZK1"

    def test_display_name_clean(self):
        b = Borehole(prefix="ZK1", folder=Path("/tmp"), hole_type=HoleType.ZK)
        assert b.display_name() == "ZK1"

    def test_available_test_suffixes_zk(self):
        b = Borehole(prefix="ZK1", folder=Path("/tmp"), hole_type=HoleType.ZK)
        assert "e" in b.available_test_suffixes()
        assert "f" in b.available_test_suffixes()

    def test_available_test_suffixes_nzk(self):
        b = Borehole(prefix="NZK1", folder=Path("/tmp"), hole_type=HoleType.NZK)
        assert "e" not in b.available_test_suffixes()

    def test_mark_dirty(self):
        b = Borehole(prefix="ZK1", folder=Path("/tmp"), hole_type=HoleType.ZK)
        b.mark_dirty("c")
        assert b.dirty is True
        assert "c" in b.dirty_suffixes


class TestProjectData:
    def test_sorted_boreholes_order(self):
        p = ProjectData()
        p.boreholes["NZK1"] = Borehole(prefix="NZK1", folder=Path("/tmp"), hole_type=HoleType.NZK)
        for prefix in ("ZK12", "ZK2", "ZK1-2", "ZK10", "ZK1"):
            p.boreholes[prefix] = Borehole(prefix=prefix, folder=Path("/tmp"), hole_type=HoleType.ZK)

        sorted_list = p.sorted_boreholes()

        assert [borehole.prefix for borehole in sorted_list] == [
            "ZK1",
            "ZK1-2",
            "ZK2",
            "ZK10",
            "ZK12",
            "NZK1",
        ]

    def test_dirty_boreholes(self):
        p = ProjectData()
        b1 = Borehole(prefix="ZK1", folder=Path("/tmp"), hole_type=HoleType.ZK, dirty=True)
        b2 = Borehole(prefix="ZK2", folder=Path("/tmp"), hole_type=HoleType.ZK)
        p.boreholes = {"ZK1": b1, "ZK2": b2}
        assert len(p.dirty_boreholes()) == 1
        assert p.dirty_boreholes()[0].prefix == "ZK1"


class TestWeathering:
    def test_labels_complete(self):
        for w in Weathering:
            assert w.value in WEATHERING_LABELS
            assert WEATHERING_LABELS[w.value] == w.label

    def test_label_values(self):
        assert Weathering.OVERBURDEN.label == "覆盖层"
        assert Weathering.FULLY_WEATHERED.label == "全风化"
