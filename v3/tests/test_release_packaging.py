from pathlib import Path


def test_release_files_use_v3_identity() -> None:
    spec = Path("borehole_v3.spec").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    build_script = Path("打包exe.bat").read_text(encoding="utf-8")

    assert 'name="钻孔数据编辑工具v3"' in spec
    assert 'name = "borehole-editor-v3"' in pyproject
    assert 'version = "3.0.0"' in pyproject
    assert "borehole_v3.spec" in build_script
    assert Path("assets/app_icon.ico").is_file()
