from pathlib import Path

from openpyxl import load_workbook

from borehole.domain.enums import HoleType
from borehole.domain.models import BasicLayer, Borehole, MainFileData, ProjectData
from borehole.domain.models import TestRecord as Record
from borehole.infrastructure.xlsx_export import export_layer_test_summary


def test_xlsx_export_handles_non_finite_numeric_text(tmp_path: Path) -> None:
    lines = ["ZK1", "nan", "inf", "", ",90", "100", "", "", "001", "", "0,0", "", "nan", "L", ",90", ""]
    borehole = Borehole(prefix="ZK1", folder=tmp_path, hole_type=HoleType.ZK, main=MainFileData(lines))
    borehole.layers = [BasicLayer(bottom_depth="10", lithology_code="11", formation="Q4")]
    borehole.tests["l"] = [Record(["nan", "2026.1.1"])]
    borehole.tests["q"] = [Record(["nan", "inf", "nan"])]
    project = ProjectData(folder=tmp_path, boreholes={"ZK1": borehole})
    target = tmp_path / "summary.xlsx"

    export_layer_test_summary(project, target)

    workbook = load_workbook(target, data_only=False)
    summary = workbook["钻孔汇总"]
    assert summary["B2"].value == "inf"
    assert summary["C2"].value == "nan"
    assert summary["F2"].value == "nan"
    assert summary["C3"].value == 0
    spt = workbook["标贯分析"]
    assert spt["D2"].value == 0
    assert spt["E2"].value == 0
