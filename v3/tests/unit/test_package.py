from pathlib import Path

import borehole


def test_v3_identity_is_consistent() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert borehole.__version__ == "3.0.0"
    assert 'name = "borehole-editor-v3"' in pyproject
    assert 'borehole-v3 = "borehole.main:main"' in pyproject
