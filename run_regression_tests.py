from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from borehole_app.models import BasicLayer, Borehole, MainFileData, ProjectData, TestRecord
from borehole_app.parser import _depth_key, parse_main_file
from borehole_app.undo import BoreholeSnapshot
from borehole_app.validation import validate_borehole
from borehole_app.writer import export_layer_test_summary, generate_borehole, write_with_backup


def test_main_file_preserves_blank_lines(folder: Path) -> None:
    main = folder / "ZK1"
    main.write_text("ZK1\n10\n\nADDR\n★\n", encoding="utf-8")
    parsed = parse_main_file(main)
    assert parsed.lines[0] == "ZK1"
    assert parsed.lines[1] == "10"
    assert parsed.lines[2] == ""
    assert parsed.lines[3] == "ADDR"


def test_gbk_backup_and_writeback(folder: Path) -> None:
    source = folder / "gbk.txt"
    source.write_text("强风化", encoding="gbk")
    write_with_backup(source, "弱风化", folder / "tmp")
    assert source.read_text(encoding="gbk") == "弱风化"
    backups = list((folder / "tmp").glob("gbk.txt.*.bak"))
    assert backups
    assert backups[0].read_text(encoding="gbk") == "强风化"


def test_new_borehole_skips_empty_test_files(folder: Path) -> None:
    borehole = Borehole(prefix="ZK_TEST", folder=folder, hole_type="ZK", is_new=True, dirty=True)
    borehole.main = MainFileData(lines=["ZK_TEST", "10"] + [""] * 14)
    borehole.layers = [BasicLayer(bottom_depth="5", lithology_code="A"), BasicLayer(bottom_depth="10", lithology_code="B")]
    borehole.tests["o"] = []
    borehole.tests["q"] = []
    borehole.tests["n"] = [TestRecord(values=["1", "2", "0.000409"])]
    borehole.dirty_suffixes.update({"o", "q", "n"})
    generate_borehole(borehole)
    assert not (folder / "ZK_TEST.-o").exists()
    assert not (folder / "ZK_TEST.-q").exists()
    assert (folder / "ZK_TEST.-n").exists()


def test_validation_extra_and_duplicate_depths(folder: Path) -> None:
    borehole = Borehole(prefix="ZK_TEST", folder=folder, hole_type="ZK")
    borehole.main = MainFileData(lines=["ZK_TEST", "10"] + [""] * 14)
    borehole.layers = [BasicLayer(bottom_depth="5", lithology_code="A"), BasicLayer(bottom_depth="10", lithology_code="B")]
    borehole.raw_texts[".-b"] = "5,X\n7,Y\n★"
    borehole.raw_texts[".-h"] = "#5\ndesc\n#5\ndup\n#8\nextra\n★"
    messages = validate_borehole(borehole)
    assert any(".-b 存在未匹配 .-c 的深度：7" in message for message in messages)
    assert any(".-h 存在未匹配 .-c 的深度：8" in message for message in messages)
    assert any(".-h 存在重复深度：5" in message for message in messages)


def test_layer_test_export_rules(folder: Path) -> None:
    borehole = Borehole(prefix="ZK1", folder=folder, hole_type="ZK")
    borehole.main = MainFileData(lines=["ZK1", "10"] + [""] * 14)
    borehole.layers = [
        BasicLayer(bottom_depth="5", lithology_code="QG02", formation="Q^s"),
        BasicLayer(bottom_depth="10", lithology_code="c321", formation="D$3s"),
    ]
    borehole.tests["n"] = [TestRecord(values=["1", "2", "0.000409"])]
    borehole.tests["m"] = [TestRecord(values=["4", "8", "7.5"])]
    project = ProjectData(folder=folder, boreholes={borehole.prefix: borehole})
    output = folder / "export.csv"
    row_count = export_layer_test_summary(project, output)
    text = output.read_text(encoding="utf-8-sig")
    assert row_count == 3
    assert "4.09E-04" in text
    assert "ZK1,1,Q^s,QG02,压水,1,4,8,7.5,透水率" in text
    assert "ZK1,2,D$3s,c321,压水,1,4,8,7.5,透水率" in text


def test_depth_key() -> None:
    assert sorted(["x", "2", "10"], key=_depth_key) == ["2", "10", "x"]


def test_undo_snapshot_is_independent(folder: Path) -> None:
    borehole = Borehole(prefix="ZK_UNDO", folder=folder, hole_type="ZK")
    borehole.main = MainFileData(lines=["ZK_UNDO", "10"] + [""] * 14)
    borehole.layers = [BasicLayer(bottom_depth="5", lithology_code="A")]
    borehole.tests["n"] = [TestRecord(values=["1", "2", "0.000409"])]
    snapshot = BoreholeSnapshot.capture(borehole)
    borehole.layers[0].bottom_depth = "6"
    borehole.tests["n"][0].values[2] = "0.0005"
    assert snapshot.layers[0].bottom_depth == "5"
    assert snapshot.tests["n"][0].values[2] == "0.000409"


def main() -> None:
    with TemporaryDirectory() as tmp:
        folder = Path(tmp)
        test_main_file_preserves_blank_lines(folder)
        test_gbk_backup_and_writeback(folder)
        test_new_borehole_skips_empty_test_files(folder)
        test_validation_extra_and_duplicate_depths(folder)
        test_layer_test_export_rules(folder)
        test_depth_key()
        test_undo_snapshot_is_independent(folder)
    print("All regression tests passed.")


if __name__ == "__main__":
    main()
