from pathlib import Path


def test_release_files_use_v3_identity() -> None:
    spec = Path("borehole_v3.spec").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    build_script = Path("打包exe.bat").read_text(encoding="utf-8")

    assert 'name="钻孔数据编辑工具v3.1"' in spec
    assert 'name = "borehole-editor-v3"' in pyproject
    assert 'version = "3.1.0"' in pyproject
    assert 'requires-python = ">=3.10,<3.14"' in pyproject
    assert 'PySide6>=6.9.0,<6.10.0' in pyproject
    assert "PySide6 6.9.x is required" in spec
    assert "borehole_v3.spec" in build_script
    assert Path("assets/app_icon.ico").is_file()
