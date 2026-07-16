from pathlib import Path

import pytest


def _main_text(prefix: str, newline: str = "\n") -> str:
    lines = [
        prefix,
        "12.5",
        "101.25",
        "测试地点",
        ",90",
        "100",
        "2026.1.1",
        "测试项目",
        "001",
        "详勘",
        "0,0",
        "2026.1.2",
        "12.5",
        "L",
        ",90",
        "测试单位",
        "★",
    ]
    return newline.join(lines)


@pytest.fixture
def legacy_project(tmp_path: Path) -> Path:
    folder = tmp_path / "legacy"
    folder.mkdir()
    (folder / "ZK1").write_text(_main_text("ZK1", "\r\n"), encoding="gbk", newline="")
    (folder / "ZK1.-c").write_text("5.0,11\r\n12.5,22\r\n★", encoding="gbk", newline="")
    (folder / "ZK1.-b").write_text("5.0,Q4\r\n12.5,K\r\n★", encoding="gbk", newline="")
    (folder / "ZK1.-d").write_text("5.0,0.11\r\n12.5,0.13\r\n★", encoding="gbk", newline="")
    (folder / "ZK1.-g").write_text("5.0,f\r\n12.5,3\r\n★", encoding="gbk", newline="")
    (folder / "ZK1.-h").write_text("#5.0\r\n粉质黏土\r\n#12.5\r\n砂岩\r\n★", encoding="gbk", newline="")
    (folder / "ZK1.-q").write_text("2.0,2.3,8\r\n★", encoding="gbk", newline="")
    (folder / "ZK1.-x").write_text("保留的未知文件\r\n", encoding="gbk", newline="")
    (folder / "H1").write_text("剖面主文件\r\n★", encoding="gbk", newline="")
    (folder / "H1.-x").write_text("剖面附属文件\r\n", encoding="gbk", newline="")
    (folder / "0nzk.-zkt").write_text("项目配置\r\n", encoding="gbk", newline="")
    return folder
