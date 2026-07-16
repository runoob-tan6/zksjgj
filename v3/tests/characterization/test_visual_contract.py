from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _render(project_root: Path, output: Path) -> None:
    helper = Path(__file__).with_name("render_window.py")
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [sys.executable, str(helper), str(project_root), str(output)],
        check=True,
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
    )


def _find_repository_root(start: Path) -> Path:
    for parent in start.parents:
        if (parent / "v2" / "src" / "borehole").is_dir() and (parent / "v3").is_dir():
            return parent
    raise RuntimeError("无法定位同时包含 v2 和 v3 的项目根目录。")


def test_v3_tabs_are_pixel_identical_to_v2(tmp_path: Path) -> None:
    v3_root = Path(__file__).resolve().parents[2]
    repository_root = _find_repository_root(Path(__file__).resolve())
    v2_root = repository_root / "v2"
    v2_output = tmp_path / "v2"
    v3_output = tmp_path / "v3"

    _render(v2_root, v2_output)
    _render(v3_root, v3_output)

    v2_images = sorted(v2_output.glob("tab-*.png"))
    v3_images = sorted(v3_output.glob("tab-*.png"))
    assert [path.name for path in v2_images] == [path.name for path in v3_images]
    assert len(v2_images) == 6
    for before, after in zip(v2_images, v3_images, strict=True):
        assert after.read_bytes() == before.read_bytes(), f"Visual mismatch in {before.name}"
