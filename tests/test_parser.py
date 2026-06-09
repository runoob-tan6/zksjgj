"""
钻孔数据编辑工具 - 解析器模块测试。

本模块包含对parser.py中函数的单元测试。
使用pytest框架，覆盖主要功能和边界情况。
"""

from __future__ import annotations

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from borehole_app.parser import (
    read_text_file,
    clean_lines,
    data_lines,
    main_file_lines,
    parse_main_file,
    parse_pair_file,
    parse_h_file,
    parse_test_file,
    parse_basic_layers,
    _depth_key,
    parse_borehole,
)
from borehole_app.models import MainFileData, BasicLayer, TestRecord, Borehole


class TestReadTextFile:
    """测试read_text_file函数。"""
    
    def test_read_utf8_file(self, tmp_path: Path) -> None:
        """测试读取UTF-8编码文件。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试内容", encoding="utf-8")
        
        result = read_text_file(test_file)
        assert result == "测试内容"
    
    def test_read_gbk_file(self, tmp_path: Path) -> None:
        """测试读取GBK编码文件。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试内容", encoding="gbk")
        
        result = read_text_file(test_file)
        assert result == "测试内容"
    
    def test_read_nonexistent_file(self, tmp_path: Path) -> None:
        """测试读取不存在的文件。"""
        test_file = tmp_path / "nonexistent.txt"
        
        with pytest.raises(FileNotFoundError):
            read_text_file(test_file)
    
    def test_read_empty_file(self, tmp_path: Path) -> None:
        """测试读取空文件。"""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("", encoding="utf-8")
        
        result = read_text_file(test_file)
        assert result == ""


class TestCleanLines:
    """测试clean_lines函数。"""
    
    def test_clean_unix_line_endings(self) -> None:
        """测试Unix换行符。"""
        text = "line1\nline2\nline3"
        result = clean_lines(text)
        assert result == ["line1", "line2", "line3"]
    
    def test_clean_windows_line_endings(self) -> None:
        """测试Windows换行符。"""
        text = "line1\r\nline2\r\nline3"
        result = clean_lines(text)
        assert result == ["line1", "line2", "line3"]
    
    def test_clean_mixed_line_endings(self) -> None:
        """测试混合换行符。"""
        text = "line1\nline2\r\nline3\r"
        result = clean_lines(text)
        assert result == ["line1", "line2", "line3"]
    
    def test_clean_empty_string(self) -> None:
        """测试空字符串。"""
        result = clean_lines("")
        assert result == []
    
    def test_clean_single_line(self) -> None:
        """测试单行文本。"""
        result = clean_lines("single line")
        assert result == ["single line"]


class TestDataLines:
    """测试data_lines函数。"""
    
    def test_data_lines_with_end_mark(self, tmp_path: Path) -> None:
        """测试包含结束标记的文件。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1\nline2\n★\n", encoding="utf-8")
        
        result = data_lines(test_file)
        assert result == ["line1", "line2"]
    
    def test_data_lines_without_end_mark(self, tmp_path: Path) -> None:
        """测试不包含结束标记的文件。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1\nline2\n", encoding="utf-8")
        
        result = data_lines(test_file)
        assert result == ["line1", "line2"]
    
    def test_data_lines_with_empty_lines(self, tmp_path: Path) -> None:
        """测试包含空行的文件。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1\n\nline2\n★\n", encoding="utf-8")
        
        result = data_lines(test_file)
        assert result == ["line1", "line2"]
    
    def test_data_lines_nonexistent_file(self, tmp_path: Path) -> None:
        """测试不存在的文件。"""
        test_file = tmp_path / "nonexistent.txt"
        
        result = data_lines(test_file)
        assert result == []


class TestMainFileLines:
    """测试main_file_lines函数。"""
    
    def test_main_file_lines_preserves_blanks(self, tmp_path: Path) -> None:
        """测试主文件保留空行。"""
        test_file = tmp_path / "main.txt"
        test_file.write_text("line1\n\nline3\n★\n", encoding="utf-8")
        
        result = main_file_lines(test_file)
        assert result == ["line1", "", "line3"]
    
    def test_main_file_lines_removes_end_mark(self, tmp_path: Path) -> None:
        """测试主文件移除结束标记。"""
        test_file = tmp_path / "main.txt"
        test_file.write_text("line1\n★\n", encoding="utf-8")
        
        result = main_file_lines(test_file)
        assert result == ["line1"]


class TestParseMainFile:
    """测试parse_main_file函数。"""
    
    def test_parse_normal_main_file(self, tmp_path: Path) -> None:
        """测试解析正常主文件。"""
        test_file = tmp_path / "ZK1"
        content = "ZK1\n10.5\n100.0\n测试地点\n90,90\n1000\n2024-01-01\n测试项目\n001\n初步勘察\n0,0\n2024-01-02\n10.0\nL\n90,90\n测试单位\n★\n"
        test_file.write_text(content, encoding="utf-8")
        
        result = parse_main_file(test_file)
        
        assert isinstance(result, MainFileData)
        assert len(result.lines) == 16
        assert result.lines[0] == "ZK1"
        assert result.lines[1] == "10.5"
        assert result.lines[2] == "100.0"
        assert result.lines[3] == "测试地点"
    
    def test_parse_main_file_with_blanks(self, tmp_path: Path) -> None:
        """测试解析包含空行的主文件。"""
        test_file = tmp_path / "ZK1"
        content = "ZK1\n10.5\n\n测试地点\n★\n"
        test_file.write_text(content, encoding="utf-8")
        
        result = parse_main_file(test_file)
        
        assert result.lines[0] == "ZK1"
        assert result.lines[1] == "10.5"
        assert result.lines[2] == ""
        assert result.lines[3] == "测试地点"
    
    def test_parse_main_file_short_content(self, tmp_path: Path) -> None:
        """测试解析内容不足16行的主文件。"""
        test_file = tmp_path / "ZK1"
        content = "ZK1\n10.5\n★\n"
        test_file.write_text(content, encoding="utf-8")
        
        result = parse_main_file(test_file)
        
        assert len(result.lines) == 16
        assert result.lines[0] == "ZK1"
        assert result.lines[1] == "10.5"
        # 剩余行应该为空字符串
        for i in range(2, 16):
            assert result.lines[i] == ""
    
    def test_parse_main_file_nonexistent(self, tmp_path: Path) -> None:
        """测试解析不存在的主文件。"""
        test_file = tmp_path / "nonexistent"
        
        result = parse_main_file(test_file)
        
        assert isinstance(result, MainFileData)
        assert len(result.lines) == 16
        # 所有行应该为空字符串
        for line in result.lines:
            assert line == ""


class TestDepthKey:
    """测试_depth_key函数。"""
    
    def test_numeric_depth(self) -> None:
        """测试数字深度。"""
        assert _depth_key("10.5") == (0, 10.5)
        assert _depth_key("0") == (0, 0.0)
        assert _depth_key("100") == (0, 100.0)
    
    def test_non_numeric_depth(self) -> None:
        """测试非数字深度。"""
        assert _depth_key("abc") == (1, "abc")
        assert _depth_key("12.5.6") == (1, "12.5.6")
        assert _depth_key("") == (1, "")
    
    def test_sorting_order(self) -> None:
        """测试排序顺序。"""
        depths = ["abc", "10", "2", "xyz", "1"]
        sorted_depths = sorted(depths, key=_depth_key)
        
        # 数字应该按数值排序，非数字按字符串排序
        assert sorted_depths == ["1", "2", "10", "abc", "xyz"]


class TestParsePairFile:
    """测试parse_pair_file函数。"""
    
    def test_parse_normal_pair_file(self, tmp_path: Path) -> None:
        """测试解析正常的配对文件。"""
        test_file = tmp_path / "test.-c"
        test_file.write_text("5,A\n10,B\n15,C\n★\n", encoding="utf-8")
        
        result = parse_pair_file(test_file)
        
        assert len(result) == 3
        assert result[0] == ("5", "A")
        assert result[1] == ("10", "B")
        assert result[2] == ("15", "C")
    
    def test_parse_pair_file_with_spaces(self, tmp_path: Path) -> None:
        """测试解析包含空格的配对文件。"""
        test_file = tmp_path / "test.-c"
        test_file.write_text("5 , A\n10 , B\n★\n", encoding="utf-8")
        
        result = parse_pair_file(test_file)
        
        assert len(result) == 2
        assert result[0] == ("5", "A")
        assert result[1] == ("10", "B")
    
    def test_parse_pair_file_empty(self, tmp_path: Path) -> None:
        """测试解析空配对文件。"""
        test_file = tmp_path / "test.-c"
        test_file.write_text("★\n", encoding="utf-8")
        
        result = parse_pair_file(test_file)
        
        assert len(result) == 0


class TestParseHFile:
    """测试parse_h_file函数。"""
    
    def test_parse_normal_h_file(self, tmp_path: Path) -> None:
        """测试解析正常的h文件。"""
        test_file = tmp_path / "test.-h"
        test_file.write_text("#5\n描述1\n#10\n描述2\n★\n", encoding="utf-8")
        
        result = parse_h_file(test_file)
        
        assert len(result) == 2
        assert result["5"] == "描述1"
        assert result["10"] == "描述2"
    
    def test_parse_h_file_with_empty_description(self, tmp_path: Path) -> None:
        """测试解析包含空描述的h文件。"""
        test_file = tmp_path / "test.-h"
        test_file.write_text("#5\n\n#10\n描述2\n★\n", encoding="utf-8")
        
        result = parse_h_file(test_file)
        
        assert len(result) == 2
        assert result["5"] == ""
        assert result["10"] == "描述2"
    
    def test_parse_h_file_missing_description(self, tmp_path: Path) -> None:
        """测试解析缺少描述的h文件。"""
        test_file = tmp_path / "test.-h"
        test_file.write_text("#5\n★\n", encoding="utf-8")
        
        result = parse_h_file(test_file)
        
        assert len(result) == 1
        assert result["5"] == ""


class TestParseBasicLayers:
    """测试parse_basic_layers函数。"""
    
    def test_parse_basic_layers_with_c_file(self, tmp_path: Path) -> None:
        """测试解析包含c文件的基础层。"""
        # 创建c文件
        c_file = tmp_path / "ZK1.-c"
        c_file.write_text("5,A\n10,B\n★\n", encoding="utf-8")
        
        # 创建b文件
        b_file = tmp_path / "ZK1.-b"
        b_file.write_text("5,Q\n10,D\n★\n", encoding="utf-8")
        
        result = parse_basic_layers(tmp_path, "ZK1")
        
        assert len(result) == 2
        assert result[0].bottom_depth == "5"
        assert result[0].lithology_code == "A"
        assert result[0].formation == "Q"
        assert result[1].bottom_depth == "10"
        assert result[1].lithology_code == "B"
        assert result[1].formation == "D"
    
    def test_parse_basic_layers_without_c_file(self, tmp_path: Path) -> None:
        """测试解析不包含c文件的基础层。"""
        # 只创建b文件
        b_file = tmp_path / "ZK1.-b"
        b_file.write_text("5,Q\n10,D\n★\n", encoding="utf-8")
        
        result = parse_basic_layers(tmp_path, "ZK1")
        
        assert len(result) == 2
        assert result[0].bottom_depth == "5"
        assert result[0].lithology_code == ""  # 没有c文件，岩性代号为空
        assert result[0].formation == "Q"
    
    def test_parse_basic_layers_empty(self, tmp_path: Path) -> None:
        """测试解析空的基础层。"""
        result = parse_basic_layers(tmp_path, "ZK1")
        
        assert len(result) == 0


class TestParseBorehole:
    """测试parse_borehole函数。"""
    
    def test_parse_zk_borehole(self, tmp_path: Path) -> None:
        """测试解析ZK钻孔。"""
        # 创建主文件
        main_file = tmp_path / "ZK1"
        main_file.write_text("ZK1\n10\n★\n", encoding="utf-8")
        
        # 创建c文件
        c_file = tmp_path / "ZK1.-c"
        c_file.write_text("5,A\n10,B\n★\n", encoding="utf-8")
        
        files = {"c": c_file}
        result = parse_borehole(tmp_path, "ZK1", files)
        
        assert isinstance(result, Borehole)
        assert result.prefix == "ZK1"
        assert result.hole_type == "ZK"
        assert result.folder == tmp_path
        assert len(result.layers) == 2
        assert result.main.lines[0] == "ZK1"
    
    def test_parse_nzk_borehole(self, tmp_path: Path) -> None:
        """测试解析NZK钻孔。"""
        # 创建主文件
        main_file = tmp_path / "NZK1"
        main_file.write_text("NZK1\n10\n★\n", encoding="utf-8")
        
        files: dict[str, Path] = {}
        result = parse_borehole(tmp_path, "NZK1", files)
        
        assert isinstance(result, Borehole)
        assert result.prefix == "NZK1"
        assert result.hole_type == "NZK"
    
    def test_parse_borehole_with_tests(self, tmp_path: Path) -> None:
        """测试解析包含试验数据的钻孔。"""
        # 创建主文件
        main_file = tmp_path / "ZK1"
        main_file.write_text("ZK1\n10\n★\n", encoding="utf-8")
        
        # 创建c文件
        c_file = tmp_path / "ZK1.-c"
        c_file.write_text("5,A\n10,B\n★\n", encoding="utf-8")
        
        # 创建试验文件
        o_file = tmp_path / "ZK1.-o"
        o_file.write_text("1,5,S1\n6,10,S2\n★\n", encoding="utf-8")
        
        files = {"c": c_file, "o": o_file}
        result = parse_borehole(tmp_path, "ZK1", files)
        
        assert len(result.tests["o"]) == 2
        assert result.tests["o"][0].values == ["1", "5", "S1"]
        assert result.tests["o"][1].values == ["6", "10", "S2"]