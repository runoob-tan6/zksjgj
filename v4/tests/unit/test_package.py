from pathlib import Path

import borehole


def test_v4_identity_is_consistent() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert borehole.__version__ == "4.0.0"
    assert 'name = "borehole-editor-v4"' in pyproject
    assert 'borehole-v4 = "borehole.main:main"' in pyproject
