"""钻孔数据编辑工具 - 数据校验模块测试。

本模块包含对validation.py中函数的单元测试。
"""

from __future__ import annotations

from pathlib import Path

from borehole_app.models import BasicLayer, Borehole, MainFileData, ProjectData, TestRecord
from borehole_app.validation import (
    _duplicate_values,
    _h_depths,
    _pair_depths,
    validate_borehole,
    validate_project,
)


class TestPairDepths:
    """测试_pair_depths函数。"""

    def test_normal_input(self) -> None:
        """测试正常输入。"""
        text = "5,A\n10,B\n15,C\n★"
        result = _pair_depths(text)
        assert result == ["5", "10", "15"]

    def test_with_spaces(self) -> None:
        """测试包含空格的输入。"""
        text = "5 , A\n10 , B\n★"
        result = _pair_depths(text)
        assert result == ["5", "10"]

    def test_empty_lines(self) -> None:
        """测试包含空行的输入。"""
        text = "5,A\n\n10,B\n★"
        result = _pair_depths(text)
        assert result == ["5", "10"]

    def test_no_comma(self) -> None:
        """测试没有逗号的行。"""
        text = "5,A\nno_comma\n10,B\n★"
        result = _pair_depths(text)
        assert result == ["5", "10"]

    def test_end_mark_only(self) -> None:
        """测试只有结束标记。"""
        text = "★"
        result = _pair_depths(text)
        assert result == []

    def test_empty_string(self) -> None:
        """测试空字符串。"""
        text = ""
        result = _pair_depths(text)
        assert result == []


class TestHDepths:
    """测试_h_depths函数。"""

    def test_normal_input(self) -> None:
        """测试正常输入。"""
        text = "#5\n描述1\n#10\n描述2\n★"
        result = _h_depths(text)
        assert result == ["5", "10"]

    def test_with_spaces(self) -> None:
        """测试包含空格的输入。"""
        text = "# 5\n描述1\n# 10\n描述2\n★"
        result = _h_depths(text)
        assert result == ["5", "10"]

    def test_non_hash_lines(self) -> None:
        """测试不以#开头的行。"""
        text = "not_depth\n#5\n描述1\n★"
        result = _h_depths(text)
        assert result == ["5"]

    def test_empty_description(self) -> None:
        """测试空描述。"""
        text = "#5\n\n#10\n描述2\n★"
        result = _h_depths(text)
        assert result == ["5", "10"]

    def test_end_mark_only(self) -> None:
        """测试只有结束标记。"""
        text = "★"
        result = _h_depths(text)
        assert result == []


class TestDuplicateValues:
    """测试_duplicate_values函数。"""

    def test_no_duplicates(self) -> None:
        """测试没有重复值。"""
        values = ["a", "b", "c"]
        result = _duplicate_values(values)
        assert result == []

    def test_with_duplicates(self) -> None:
        """测试有重复值。"""
        values = ["a", "b", "a", "c", "b"]
        result = _duplicate_values(values)
        assert result == ["a", "b"]

    def test_order_preserved(self) -> None:
        """测试保持顺序。"""
        values = ["b", "a", "b", "a"]
        result = _duplicate_values(values)
        assert result == ["b", "a"]

    def test_empty_list(self) -> None:
        """测试空列表。"""
        result = _duplicate_values([])
        assert result == []

    def test_single_item(self) -> None:
        """测试单个元素。"""
        result = _duplicate_values(["a"])
        assert result == []


class TestValidateBorehole:
    """测试validate_borehole函数。"""

    def test_valid_borehole(self) -> None:
        """测试有效的钻孔。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code="A"),
            BasicLayer(bottom_depth="10", lithology_code="B"),
        ]

        messages = validate_borehole(borehole)

        assert len(messages) == 0

    def test_missing_hole_id(self) -> None:
        """测试缺少钻孔编号。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["", "10"] + [""] * 14)

        messages = validate_borehole(borehole)

        assert any("钻孔编号" in msg for msg in messages)

    def test_missing_depth(self) -> None:
        """测试缺少孔深。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", ""] + [""] * 14)

        messages = validate_borehole(borehole)

        assert any("孔深" in msg for msg in messages)

    def test_invalid_depth(self) -> None:
        """测试无效的孔深。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "abc"] + [""] * 14)

        messages = validate_borehole(borehole)

        assert any("有效数字" in msg for msg in messages)

    def test_layer_depth_not_increasing(self) -> None:
        """测试层底深度未递增。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="10", lithology_code="A"),
            BasicLayer(bottom_depth="5", lithology_code="B"),  # 深度减小
        ]

        messages = validate_borehole(borehole)

        assert any("未递增" in msg for msg in messages)

    def test_missing_lithology_code(self) -> None:
        """测试缺少岩性代号。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code=""),
        ]

        messages = validate_borehole(borehole)

        assert any("岩性代号" in msg for msg in messages)

    def test_invalid_weathering(self) -> None:
        """测试无效的风化代码。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code="A", weathering="9"),
        ]

        messages = validate_borehole(borehole)

        assert any("风化代码" in msg for msg in messages)

    def test_depth_mismatch(self) -> None:
        """测试孔深与层底深度不一致。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code="A"),
        ]

        messages = validate_borehole(borehole)

        assert any("不一致" in msg for msg in messages)

    def test_extra_depth_in_b_file(self) -> None:
        """测试b文件有额外深度。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code="A"),
        ]
        borehole.raw_texts[".-b"] = "5,Q\n7,D\n★"

        messages = validate_borehole(borehole)

        assert any(".-b" in msg and "7" in msg for msg in messages)

    def test_duplicate_h_depths(self) -> None:
        """测试h文件有重复深度。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code="A"),
        ]
        borehole.raw_texts[".-h"] = "#5\ndesc1\n#5\ndesc2\n★"

        messages = validate_borehole(borehole)

        assert any("重复深度" in msg and "5" in msg for msg in messages)

    def test_nzk_invalid_test_suffix(self) -> None:
        """测试NZK钻孔有无效的试验类型。"""
        borehole = Borehole(prefix="NZK1", folder=Path("/data"), hole_type="NZK")
        borehole.main = MainFileData(lines=["NZK1", "10"] + [""] * 14)
        borehole.tests["e"] = [TestRecord(values=["1", "5", "80"])]

        messages = validate_borehole(borehole)

        assert any("NZK" in msg and ".-e" in msg for msg in messages)


class TestValidateProject:
    """测试validate_project函数。"""

    def test_valid_project(self) -> None:
        """测试有效的项目。"""
        project = ProjectData(folder=Path("/data"))
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code="A"),
            BasicLayer(bottom_depth="10", lithology_code="B"),
        ]
        project.boreholes["ZK1"] = borehole

        messages = validate_project(project)

        assert len(messages) == 0

    def test_invalid_project(self) -> None:
        """测试无效的项目。"""
        project = ProjectData(folder=Path("/data"))
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["", ""] + [""] * 14)
        project.boreholes["ZK1"] = borehole

        messages = validate_project(project)

        assert len(messages) > 0
        assert all("ZK1:" in msg for msg in messages)
