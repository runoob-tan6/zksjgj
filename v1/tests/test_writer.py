"""钻孔数据编辑工具 - 文件写入模块测试。

本模块包含对writer.py中函数的单元测试。
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from borehole_app.models import BasicLayer, Borehole, MainFileData, ProjectData
from borehole_app.models import TestRecord as ModelTestRecord
from borehole_app.writer import (
    backup_existing_file,
    build_test_file_lines,
    delete_borehole_files,
    export_layer_test_summary,
    generate_borehole,
    generate_dirty_boreholes,
    make_file_text,
    normalize_for_compare,
    read_existing_text,
    read_existing_text_with_encoding,
    render_h_file,
    render_main_file,
    render_pair_file,
    render_test_file,
    write_with_backup,
)


class TestMakeFileText:
    """测试make_file_text函数。"""

    def test_normal_input(self) -> None:
        """测试正常输入。"""
        lines = ["line1", "line2", "line3"]
        result = make_file_text(lines)
        assert result == "line1\nline2\nline3\n★"

    def test_empty_input(self) -> None:
        """测试空输入。"""
        result = make_file_text([])
        assert result == "★"

    def test_single_line(self) -> None:
        """测试单行输入。"""
        result = make_file_text(["single"])
        assert result == "single\n★"

    def test_with_empty_strings(self) -> None:
        """测试包含空字符串的输入。"""
        lines = ["line1", "", "line3"]
        result = make_file_text(lines)
        assert result == "line1\n\nline3\n★"


class TestNormalizeForCompare:
    """测试normalize_for_compare函数。"""

    def test_none_input(self) -> None:
        """测试None输入。"""
        result = normalize_for_compare(None)
        assert result is None

    def test_unix_line_endings(self) -> None:
        """测试Unix换行符。"""
        result = normalize_for_compare("line1\nline2\n")
        assert result == "line1\nline2"

    def test_windows_line_endings(self) -> None:
        """测试Windows换行符。"""
        result = normalize_for_compare("line1\r\nline2\r\n")
        assert result == "line1\nline2"

    def test_mixed_line_endings(self) -> None:
        """测试混合换行符。"""
        result = normalize_for_compare("line1\nline2\r\nline3\r")
        assert result == "line1\nline2\nline3"

    def test_trailing_newlines(self) -> None:
        """测试末尾换行符。"""
        result = normalize_for_compare("content\n\n\n")
        assert result == "content"


class TestReadWriteFunctions:
    """测试读写相关函数。"""

    def test_read_nonexistent_file(self, tmp_path: Path) -> None:
        """测试读取不存在的文件。"""
        result = read_existing_text(tmp_path / "nonexistent.txt")
        assert result is None

    def test_read_existing_file(self, tmp_path: Path) -> None:
        """测试读取存在的文件。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        result = read_existing_text(test_file)
        assert result == "content"

    def test_read_existing_text_with_encoding_utf8(self, tmp_path: Path) -> None:
        """测试读取UTF-8编码文件。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试内容", encoding="utf-8")

        text, encoding = read_existing_text_with_encoding(test_file)
        assert text == "测试内容"
        assert encoding == "utf-8"

    def test_read_existing_text_with_encoding_gbk(self, tmp_path: Path) -> None:
        """测试读取GBK编码文件。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试内容", encoding="gbk")

        text, encoding = read_existing_text_with_encoding(test_file)
        assert text == "测试内容"
        assert encoding == "gbk"

    def test_read_existing_text_with_encoding_nonexistent(self, tmp_path: Path) -> None:
        """测试读取不存在的文件。"""
        text, encoding = read_existing_text_with_encoding(tmp_path / "nonexistent.txt")
        assert text is None
        assert encoding == "utf-8"


class TestBackupExistingFile:
    """测试backup_existing_file函数。"""

    def test_backup_existing_file(self, tmp_path: Path) -> None:
        """测试备份存在的文件。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        backup_path = backup_existing_file(test_file)

        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == "content"
        assert backup_path.name.startswith("test.txt.")
        assert backup_path.name.endswith(".bak")

    def test_backup_nonexistent_file(self, tmp_path: Path) -> None:
        """测试备份不存在的文件。"""
        result = backup_existing_file(tmp_path / "nonexistent.txt")
        assert result is None

    def test_backup_to_custom_folder(self, tmp_path: Path) -> None:
        """测试备份到自定义文件夹。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        backup_folder = tmp_path / "backups"
        backup_path = backup_existing_file(test_file, backup_folder)

        assert backup_path is not None
        assert backup_path.parent == backup_folder
        assert backup_path.exists()


class TestWriteWithBackup:
    """测试write_with_backup函数。"""

    def test_write_new_file(self, tmp_path: Path) -> None:
        """测试写入新文件。"""
        test_file = tmp_path / "test.txt"

        result = write_with_backup(test_file, "new content")

        assert result is True
        assert test_file.read_text(encoding="utf-8") == "new content"

    def test_write_existing_file_same_content(self, tmp_path: Path) -> None:
        """测试写入相同内容。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        result = write_with_backup(test_file, "content")

        assert result is False

    def test_write_existing_file_different_content(self, tmp_path: Path) -> None:
        """测试写入不同内容。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("old content", encoding="utf-8")

        result = write_with_backup(test_file, "new content")

        assert result is True
        assert test_file.read_text(encoding="utf-8") == "new content"
        # 检查备份文件
        backups = list(tmp_path.glob("test.txt.*.bak"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "old content"

    def test_write_preserves_gbk_encoding(self, tmp_path: Path) -> None:
        """测试写入保留GBK编码。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("旧内容", encoding="gbk")

        write_with_backup(test_file, "新内容")

        assert test_file.read_text(encoding="gbk") == "新内容"


class TestRenderFunctions:
    """测试渲染函数。"""

    def test_render_main_file(self) -> None:
        """测试渲染主文件。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)

        result = render_main_file(borehole)

        lines = result.split("\n")
        assert lines[0] == "ZK1"
        assert lines[1] == "10"
        assert lines[12] == "10"  # 套管下入深度等于孔深
        assert lines[-1] == "★"

    def test_render_pair_file(self) -> None:
        """测试渲染配对文件。"""
        rows = [("5", "A"), ("10", "B")]
        result = render_pair_file(rows)

        lines = result.split("\n")
        assert lines[0] == "5,A"
        assert lines[1] == "10,B"
        assert lines[-1] == "★"

    def test_render_pair_file_skip_empty_value(self) -> None:
        """测试渲染配对文件跳过空值。"""
        rows = [("5", "A"), ("10", "")]
        result = render_pair_file(rows, skip_empty_value=True)

        lines = result.split("\n")
        assert len(lines) == 2  # 只有一行数据 + 结束标记
        assert lines[0] == "5,A"

    def test_render_h_file(self) -> None:
        """测试渲染岩性描述文件。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.layers = [
            BasicLayer(bottom_depth="5", description="花岗岩"),
            BasicLayer(bottom_depth="10", description="片麻岩"),
        ]

        result = render_h_file(borehole)

        lines = result.split("\n")
        assert lines[0] == "#5"
        assert lines[1] == "花岗岩"
        assert lines[2] == "#10"
        assert lines[3] == "片麻岩"
        assert lines[-1] == "★"

    def test_build_test_file_lines(self) -> None:
        """测试生成试验文件行。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.tests["o"] = [
            ModelTestRecord(values=["1", "5", "S1"]),
            ModelTestRecord(values=["6", "10", "S2"]),
        ]

        result = build_test_file_lines(borehole, "o")

        assert len(result) == 2
        assert result[0] == "1,5,S1"
        assert result[1] == "6,10,S2"

    def test_build_test_file_lines_with_empty_values(self) -> None:
        """测试生成试验文件行（包含空值）。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.tests["o"] = [
            ModelTestRecord(values=["1", "5", "S1", ""]),
        ]

        result = build_test_file_lines(borehole, "o")

        assert len(result) == 1
        assert result[0] == "1,5,S1"

    def test_render_test_file(self) -> None:
        """测试渲染试验文件。"""
        borehole = Borehole(prefix="ZK1", folder=Path("/data"), hole_type="ZK")
        borehole.tests["o"] = [
            ModelTestRecord(values=["1", "5", "S1"]),
        ]

        result = render_test_file(borehole, "o")

        lines = result.split("\n")
        assert lines[0] == "1,5,S1"
        assert lines[-1] == "★"


class TestGenerateBorehole:
    """测试generate_borehole函数。"""

    def test_generate_new_borehole(self, tmp_path: Path) -> None:
        """测试生成新钻孔。"""
        borehole = Borehole(prefix="ZK1", folder=tmp_path, hole_type="ZK", is_new=True, dirty=True)
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code="A"),
            BasicLayer(bottom_depth="10", lithology_code="B"),
        ]

        generated = generate_borehole(borehole)

        assert len(generated) > 0
        assert (tmp_path / "ZK1").exists()
        assert (tmp_path / "ZK1.-c").exists()
        assert not borehole.is_new
        assert not borehole.dirty

    def test_generate_borehole_with_old_prefix(self, tmp_path: Path) -> None:
        """测试生成钻孔（带旧前缀）。"""
        # 创建旧文件
        old_file = tmp_path / "ZK1"
        old_file.write_text("old content", encoding="utf-8")

        borehole = Borehole(prefix="ZK2", folder=tmp_path, hole_type="ZK", is_new=True, dirty=True)
        borehole.main = MainFileData(lines=["ZK2", "10"] + [""] * 14)
        borehole.existing_suffixes = {"main"}

        generate_borehole(borehole, old_prefix="ZK1")

        assert (tmp_path / "ZK2").exists()
        assert not (tmp_path / "ZK1").exists()
        # 检查备份
        backups = list((tmp_path / "tmp").glob("ZK1.*.bak"))
        assert len(backups) == 1

    def test_generate_borehole_deletes_empty_test_files(self, tmp_path: Path) -> None:
        """测试试验数据被清空后保存时删除对应文件。"""
        # 创建钻孔，模拟已有试验文件
        borehole = Borehole(prefix="ZK1", folder=tmp_path, hole_type="ZK", is_new=True, dirty=True)
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="10", lithology_code="A"),
        ]
        # 添加试验数据
        borehole.tests["o"] = [ModelTestRecord(values=["1", "5", "S1"])]
        borehole.existing_suffixes = {"main", "c", "o"}

        # 第一次保存：生成试验文件
        generated = generate_borehole(borehole)
        test_file = tmp_path / "ZK1.-o"
        assert test_file.exists()
        assert test_file in generated

        # 清空试验数据
        borehole.tests["o"] = []
        borehole.dirty_suffixes.add("o")

        # 第二次保存：试验文件应该被删除
        generated = generate_borehole(borehole)
        assert not test_file.exists()
        # 检查备份已创建
        backups = list((tmp_path / "tmp").glob("ZK1.-o.*.bak"))
        assert len(backups) == 1


class TestExportLayerTestSummary:
    """测试export_layer_test_summary函数。"""

    def test_export_with_data(self, tmp_path: Path) -> None:
        """测试导出有数据的情况。"""
        project = ProjectData(folder=tmp_path)
        borehole = Borehole(prefix="ZK1", folder=tmp_path, hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code="A", formation="Q"),
            BasicLayer(bottom_depth="10", lithology_code="B", formation="D"),
        ]
        borehole.tests["o"] = [
            ModelTestRecord(values=["1", "5", "S1"]),
        ]
        project.boreholes["ZK1"] = borehole

        output_file = tmp_path / "export.csv"
        row_count = export_layer_test_summary(project, output_file)

        assert row_count > 0
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8-sig")
        assert "钻孔编号" in content
        assert "ZK1" in content

    def test_export_injection_result_uses_scientific_notation(self, tmp_path: Path) -> None:
        """测试注水试验导出结果值使用科学记数法。"""
        project = ProjectData(folder=tmp_path)
        borehole = Borehole(prefix="ZK1", folder=tmp_path, hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code="A", formation="Q"),
        ]
        borehole.tests["n"] = [
            ModelTestRecord(values=["1", "2", "0.000409"]),
        ]
        project.boreholes["ZK1"] = borehole

        output_file = tmp_path / "export.csv"
        row_count = export_layer_test_summary(project, output_file)

        assert row_count == 1
        content = output_file.read_text(encoding="utf-8-sig")
        assert "试验深度" in content
        assert "试验起始深度" not in content
        assert "试验终止深度" not in content
        assert "数量" not in content.splitlines()[0]
        assert "ZK1,1,Q,A,注水,1-2,4.09E-04,渗透系数" in content
        assert "统计汇总" in content
        assert "Q,A,注水,1,4.09E-04,4.09E-04,4.09E-04" in content
        detail_row = content.splitlines()[1]
        assert "0.000409" not in detail_row

    def test_export_xlsx_injection_result_cell_uses_scientific_number_format(self, tmp_path: Path) -> None:
        """测试 XLSX 注水结果值是数值单元格，并使用科学记数格式。"""
        project = ProjectData(folder=tmp_path)
        borehole = Borehole(prefix="ZK1", folder=tmp_path, hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code="A", formation="Q"),
        ]
        borehole.tests["n"] = [
            ModelTestRecord(values=["1", "2", "4.09E-04"]),
        ]
        project.boreholes["ZK1"] = borehole

        output_file = tmp_path / "export.xlsx"
        row_count = export_layer_test_summary(project, output_file)

        assert row_count == 1
        with zipfile.ZipFile(output_file) as workbook:
            sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
            styles_xml = workbook.read("xl/styles.xml").decode("utf-8")

        assert 'r="G2" s="1"' in sheet_xml
        assert "<v>0.000409</v>" in sheet_xml
        assert 'formatCode="0.00E+00"' in styles_xml
        assert '<c r="G2" t="inlineStr"><is><t>4.09E-04</t></is></c>' not in sheet_xml

    def test_export_pressure_test_uses_start_depth_layer_only(self, tmp_path: Path) -> None:
        """测试跨层压水试验只按起始深度所在层导出。"""
        project = ProjectData(folder=tmp_path)
        borehole = Borehole(prefix="ZK1", folder=tmp_path, hole_type="ZK")
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code="A", formation="Q"),
            BasicLayer(bottom_depth="10", lithology_code="B", formation="D"),
        ]
        borehole.tests["m"] = [
            ModelTestRecord(values=["4", "8", "7.5"]),
        ]
        project.boreholes["ZK1"] = borehole

        output_file = tmp_path / "export.csv"
        row_count = export_layer_test_summary(project, output_file)

        assert row_count == 1
        content = output_file.read_text(encoding="utf-8-sig")
        assert "ZK1,1,Q,A,压水,4-8,7.5,透水率" in content
        assert "ZK1,2,D,B,压水,4-8,7.5,透水率" not in content

    def test_export_uses_grouped_formation_for_blank_layer(self, tmp_path: Path) -> None:
        project = ProjectData(folder=tmp_path)
        borehole = Borehole(prefix="NZK16", folder=tmp_path, hole_type="NZK")
        borehole.main = MainFileData(lines=["NZK16", "14.2"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="2", lithology_code="QB05", formation=""),
            BasicLayer(bottom_depth="4.2", lithology_code="QF09", formation="Q$4^al"),
            BasicLayer(bottom_depth="6.8", lithology_code="QB05", formation=""),
            BasicLayer(bottom_depth="9.2", lithology_code="QF09", formation="Q$2^al"),
            BasicLayer(bottom_depth="14.2", lithology_code="B043", formation="P$tln"),
        ]
        borehole.tests["o"] = [
            ModelTestRecord(values=["0.4", "0.8", "ZK16-1"]),
        ]
        project.boreholes["NZK16"] = borehole

        output_file = tmp_path / "export.csv"
        row_count = export_layer_test_summary(project, output_file)

        assert row_count == 1
        content = output_file.read_text(encoding="utf-8-sig")
        assert "NZK16,1,Q$4^al,QB05" in content
        assert "NZK16,1,,QB05" not in content

    def test_export_sorts_same_group_by_borehole_number(self, tmp_path: Path) -> None:
        project = ProjectData(folder=tmp_path)
        for prefix, sample in [("NZK11", "S11"), ("NZK28", "S28"), ("NZK6", "S6")]:
            borehole = Borehole(prefix=prefix, folder=tmp_path, hole_type="NZK")
            borehole.main = MainFileData(lines=[prefix, "10"] + [""] * 14)
            borehole.layers = [
                BasicLayer(bottom_depth="10", lithology_code="QB05", formation="Q$2^al"),
            ]
            borehole.tests["o"] = [
                ModelTestRecord(values=["1", "2", sample]),
            ]
            project.boreholes[prefix] = borehole

        output_file = tmp_path / "export.csv"
        row_count = export_layer_test_summary(project, output_file)

        assert row_count == 3
        lines = output_file.read_text(encoding="utf-8-sig").splitlines()
        detail_lines = []
        for line in lines[1:]:
            if not line:
                break
            detail_lines.append(line)
        assert [line.split(",", 1)[0] for line in detail_lines] == ["NZK6", "NZK11", "NZK28"]

    def test_export_appends_grouped_statistics(self, tmp_path: Path) -> None:
        project = ProjectData(folder=tmp_path)
        borehole = Borehole(prefix="NZK1", folder=tmp_path, hole_type="NZK")
        borehole.main = MainFileData(lines=["NZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="10", lithology_code="QB05", formation="Q$2^al"),
        ]
        borehole.tests["q"] = [
            ModelTestRecord(values=["1", "2", "7"]),
            ModelTestRecord(values=["3", "4", "11"]),
        ]
        borehole.tests["n"] = [
            ModelTestRecord(values=["5", "6", "0.0002"]),
            ModelTestRecord(values=["7", "8", "0.0004"]),
        ]
        borehole.tests["o"] = [
            ModelTestRecord(values=["8", "9", "S1"]),
        ]
        project.boreholes["NZK1"] = borehole

        output_file = tmp_path / "export.csv"
        row_count = export_layer_test_summary(project, output_file)

        assert row_count == 5
        content = output_file.read_text(encoding="utf-8-sig")
        assert "统计汇总" in content
        assert "地层时代/成因,岩性代号,试验类型,试验数,最大值,最小值,平均值" in content
        assert "Q$2^al,QB05,取样,1,,," in content
        assert "Q$2^al,QB05,标贯,2,11,7,9.0" in content
        assert "Q$2^al,QB05,注水,2,4.00E-04,2.00E-04,3.00E-04" in content

    def test_export_xlsx_injection_summary_uses_scientific_number_format(self, tmp_path: Path) -> None:
        project = ProjectData(folder=tmp_path)
        borehole = Borehole(prefix="NZK1", folder=tmp_path, hole_type="NZK")
        borehole.main = MainFileData(lines=["NZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="10", lithology_code="QB05", formation="Q$2^al"),
        ]
        borehole.tests["n"] = [
            ModelTestRecord(values=["5", "6", "0.0002"]),
            ModelTestRecord(values=["7", "8", "0.0004"]),
        ]
        project.boreholes["NZK1"] = borehole

        output_file = tmp_path / "export.xlsx"
        row_count = export_layer_test_summary(project, output_file)

        assert row_count == 2
        with zipfile.ZipFile(output_file) as workbook:
            sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
            styles_xml = workbook.read("xl/styles.xml").decode("utf-8")

        assert 'r="E7" s="1"' in sheet_xml
        assert 'r="F7" s="1"' in sheet_xml
        assert 'r="G7" s="1"' in sheet_xml
        assert "<v>0.0004</v>" in sheet_xml
        assert "<v>0.0002</v>" in sheet_xml
        assert "<v>0.0003</v>" in sheet_xml
        assert 'formatCode="0.00E+00"' in styles_xml

    def test_export_empty_project(self, tmp_path: Path) -> None:
        """测试导出空项目。"""
        project = ProjectData(folder=tmp_path)

        output_file = tmp_path / "export.csv"
        row_count = export_layer_test_summary(project, output_file)

        assert row_count == 0
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8-sig")
        assert "钻孔编号" in content


class TestDeleteBoreholeFiles:
    """测试delete_borehole_files函数。"""

    def test_delete_existing_files(self, tmp_path: Path) -> None:
        """测试删除存在的文件。"""
        borehole = Borehole(prefix="ZK1", folder=tmp_path, hole_type="ZK")
        borehole.existing_suffixes = {"main", "c"}

        # 创建文件
        (tmp_path / "ZK1").write_text("content", encoding="utf-8")
        (tmp_path / "ZK1.-c").write_text("content", encoding="utf-8")

        deleted = delete_borehole_files(borehole)

        assert len(deleted) == 2
        assert not (tmp_path / "ZK1").exists()
        assert not (tmp_path / "ZK1.-c").exists()
        # 检查备份
        backups = list((tmp_path / "tmp").glob("ZK1*.bak"))
        assert len(backups) == 2


class TestGenerateDirtyBoreholes:
    """测试generate_dirty_boreholes函数。"""

    def test_generate_dirty_boreholes(self, tmp_path: Path) -> None:
        """测试生成有修改的钻孔。"""
        project = ProjectData(folder=tmp_path)

        borehole = Borehole(prefix="ZK1", folder=tmp_path, hole_type="ZK", is_new=True, dirty=True)
        borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
        borehole.layers = [
            BasicLayer(bottom_depth="5", lithology_code="A"),
        ]
        project.boreholes["ZK1"] = borehole

        generated = generate_dirty_boreholes(project)

        assert len(generated) > 0
        assert (tmp_path / "ZK1").exists()
