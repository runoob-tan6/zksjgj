"""钻孔数据编辑工具 - 数据模型模块测试。

本模块包含对models.py中类和函数的单元测试。
"""

from __future__ import annotations

from pathlib import Path

from borehole_app.models import (
    BASE_SUFFIX_NAMES,
    BASE_SUFFIXES,
    EDITABLE_MAIN_INDICES,
    END_MARK,
    FIXED_MAIN_DEFAULTS,
    MAIN_FIELD_NAMES,
    NZK_TEST_SUFFIXES,
    TEST_SUFFIX_NAMES,
    WEATHERING_MAP,
    ZK_TEST_SUFFIXES,
    BasicLayer,
    Borehole,
    MainFileData,
    ProjectData,
)
from borehole_app.models import (
    TestRecord as ModelTestRecord,
)


class TestMainFileData:
    """测试MainFileData类。"""

    def test_default_lines(self) -> None:
        """测试默认行数。"""
        data = MainFileData()
        assert len(data.lines) == 16

    def test_normalized_lines_short_input(self) -> None:
        """测试短输入的标准化。"""
        data = MainFileData(lines=["ZK1", "10"])
        result = data.normalized_lines()

        assert len(result) == 16
        assert result[0] == "ZK1"
        assert result[1] == "10"
        # 检查默认值
        assert result[4] == ",90"
        assert result[8] == "001"
        assert result[10] == "0,0"
        assert result[13] == "L"
        assert result[14] == ",90"

    def test_normalized_lines_long_input(self) -> None:
        """测试长输入的标准化。"""
        lines = [f"line{i}" for i in range(20)]
        data = MainFileData(lines=lines)
        result = data.normalized_lines()

        assert len(result) == 16
        assert result[0] == "line0"
        assert result[15] == "line15"

    def test_hole_id_property(self) -> None:
        """测试hole_id属性。"""
        data = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        assert data.hole_id == "ZK1"

    def test_hole_id_setter(self) -> None:
        """测试hole_id设置器。"""
        data = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        data.hole_id = "ZK2"
        assert data.hole_id == "ZK2"
        assert data.lines[0] == "ZK2"

    def test_depth_property(self) -> None:
        """测试depth属性。"""
        data = MainFileData(lines=["ZK1", "10.5"] + [""] * 14)
        assert data.depth == "10.5"


class TestBasicLayer:
    """测试BasicLayer类。"""

    def test_default_values(self) -> None:
        """测试默认值。"""
        layer = BasicLayer()
        assert layer.bottom_depth == ""
        assert layer.lithology_code == ""
        assert layer.formation == ""
        assert layer.structure == ""
        assert layer.weathering == ""
        assert layer.description == ""

    def test_custom_values(self) -> None:
        """测试自定义值。"""
        layer = BasicLayer(
            bottom_depth="5", lithology_code="A", formation="Q", structure="S", weathering="1", description="花岗岩"
        )
        assert layer.bottom_depth == "5"
        assert layer.lithology_code == "A"
        assert layer.formation == "Q"
        assert layer.structure == "S"
        assert layer.weathering == "1"
        assert layer.description == "花岗岩"


class TestTestRecord:
    """测试TestRecord类。"""

    def test_default_values(self) -> None:
        """测试默认值。"""
        record = ModelTestRecord()
        assert record.values == []

    def test_custom_values(self) -> None:
        """测试自定义值。"""
        record = ModelTestRecord(values=["1", "5", "0.000409"])
        assert record.values == ["1", "5", "0.000409"]


class TestBorehole:
    """测试Borehole类。"""

    def test_display_name_new(self) -> None:
        """测试新建钻孔的显示名称。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK", is_new=True)
        assert borehole.display_name() == "*ZK1"

    def test_display_name_dirty(self) -> None:
        """测试有修改的钻孔的显示名称。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK", dirty=True)
        assert borehole.display_name() == "*ZK1"

    def test_display_name_clean(self) -> None:
        """测试已保存钻孔的显示名称。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        assert borehole.display_name() == "ZK1"

    def test_available_test_suffixes_zk(self) -> None:
        """测试ZK钻孔的可用试验后缀。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        suffixes = borehole.available_test_suffixes()

        assert "e" in suffixes
        assert "f" in suffixes
        assert "m" in suffixes
        assert "n" in suffixes
        assert "o" in suffixes
        assert "q" in suffixes
        assert "l" in suffixes

    def test_available_test_suffixes_nzk(self) -> None:
        """测试NZK钻孔的可用试验后缀。"""
        borehole = Borehole(prefix="NZK1", folder=Path("/data"), hole_type="NZK")
        suffixes = borehole.available_test_suffixes()

        assert "e" not in suffixes
        assert "f" not in suffixes
        assert "m" not in suffixes
        assert "n" in suffixes
        assert "o" in suffixes
        assert "q" in suffixes
        assert "l" in suffixes

    def test_mark_dirty(self) -> None:
        """测试标记修改。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")

        assert not borehole.dirty
        assert len(borehole.dirty_suffixes) == 0

        borehole.mark_dirty("c")

        assert borehole.dirty
        assert "c" in borehole.dirty_suffixes

    def test_mark_dirty_without_suffix(self) -> None:
        """测试不带后缀的标记修改。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")

        borehole.mark_dirty()

        assert borehole.dirty
        assert len(borehole.dirty_suffixes) == 0


class TestProjectData:
    """测试ProjectData类。"""

    def test_sorted_boreholes(self) -> None:
        """测试钻孔排序。"""
        project = ProjectData(folder=Path("/data"))

        # 添加不同类型的钻孔
        zk1 = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        nzk1 = Borehole(prefix="NZK1", folder=Path("/data"), hole_type="NZK")
        zk2 = Borehole(prefix="ZK2", folder=Path("/data"), hole_type="ZK")

        project.boreholes = {"ZK1": zk1, "NZK1": nzk1, "ZK2": zk2}

        sorted_list = project.sorted_boreholes()

        # ZK类型在前，NZK类型在后
        assert sorted_list[0].prefix == "ZK1"
        assert sorted_list[1].prefix == "ZK2"
        assert sorted_list[2].prefix == "NZK1"

    def test_dirty_boreholes(self) -> None:
        """测试获取有修改的钻孔。"""
        project = ProjectData(folder=Path("/data"))

        zk1 = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        zk2 = Borehole(prefix="ZK2", folder=Path("/data"), hole_type="ZK", dirty=True)
        zk3 = Borehole(prefix="ZK3", folder=Path("/data"), hole_type="ZK", is_new=True)

        project.boreholes = {"ZK1": zk1, "ZK2": zk2, "ZK3": zk3}

        dirty_list = project.dirty_boreholes()

        assert len(dirty_list) == 2
        assert zk2 in dirty_list
        assert zk3 in dirty_list
        assert zk1 not in dirty_list


class TestConstants:
    """测试常量定义。"""

    def test_end_mark(self) -> None:
        """测试结束标记。"""
        assert END_MARK == "★"

    def test_main_field_names_length(self) -> None:
        """测试主文件字段名称数量。"""
        assert len(MAIN_FIELD_NAMES) == 16

    def test_editable_main_indices(self) -> None:
        """测试可编辑字段索引。"""
        assert 0 in EDITABLE_MAIN_INDICES  # 钻孔编号
        assert 1 in EDITABLE_MAIN_INDICES  # 孔深
        assert 4 not in EDITABLE_MAIN_INDICES  # 钻孔方位、倾角（固定）

    def test_fixed_main_defaults(self) -> None:
        """测试固定字段默认值。"""
        assert FIXED_MAIN_DEFAULTS[4] == ",90"
        assert FIXED_MAIN_DEFAULTS[8] == "001"
        assert FIXED_MAIN_DEFAULTS[10] == "0,0"
        assert FIXED_MAIN_DEFAULTS[13] == "L"
        assert FIXED_MAIN_DEFAULTS[14] == ",90"

    def test_weathering_map(self) -> None:
        """测试风化程度映射。"""
        assert WEATHERING_MAP["f"] == "覆盖层"
        assert WEATHERING_MAP["4"] == "全风化"
        assert WEATHERING_MAP["3"] == "强风化"
        assert WEATHERING_MAP["2"] == "弱风化"
        assert WEATHERING_MAP["1"] == "微风化"

    def test_base_suffixes(self) -> None:
        """测试基础数据后缀。"""
        assert "b" in BASE_SUFFIXES
        assert "c" in BASE_SUFFIXES
        assert "d" in BASE_SUFFIXES
        assert "g" in BASE_SUFFIXES
        assert "h" in BASE_SUFFIXES

    def test_zk_test_suffixes(self) -> None:
        """测试ZK试验数据后缀。"""
        assert "e" in ZK_TEST_SUFFIXES
        assert "f" in ZK_TEST_SUFFIXES
        assert "m" in ZK_TEST_SUFFIXES
        assert "n" in ZK_TEST_SUFFIXES
        assert "o" in ZK_TEST_SUFFIXES
        assert "q" in ZK_TEST_SUFFIXES
        assert "l" in ZK_TEST_SUFFIXES

    def test_nzk_test_suffixes(self) -> None:
        """测试NZK试验数据后缀。"""
        assert "e" not in NZK_TEST_SUFFIXES
        assert "f" not in NZK_TEST_SUFFIXES
        assert "m" not in NZK_TEST_SUFFIXES
        assert "n" in NZK_TEST_SUFFIXES
        assert "o" in NZK_TEST_SUFFIXES
        assert "q" in NZK_TEST_SUFFIXES
        assert "l" in NZK_TEST_SUFFIXES

    def test_test_suffix_names(self) -> None:
        """测试试验数据后缀名称。"""
        assert TEST_SUFFIX_NAMES["e"] == "岩芯获得率"
        assert TEST_SUFFIX_NAMES["f"] == "RQD值"
        assert TEST_SUFFIX_NAMES["m"] == "透水率"
        assert TEST_SUFFIX_NAMES["n"] == "渗透系数"
        assert TEST_SUFFIX_NAMES["o"] == "岩芯取样"
        assert TEST_SUFFIX_NAMES["q"] == "标贯击数"
        assert TEST_SUFFIX_NAMES["l"] == "稳定水位"

    def test_base_suffix_names(self) -> None:
        """测试基础数据后缀名称。"""
        assert BASE_SUFFIX_NAMES["b"] == "地层时代"
        assert BASE_SUFFIX_NAMES["c"] == "岩性代号"
        assert BASE_SUFFIX_NAMES["d"] == "钻孔结构"
        assert BASE_SUFFIX_NAMES["g"] == "风化程度"
        assert BASE_SUFFIX_NAMES["h"] == "岩性描述"
