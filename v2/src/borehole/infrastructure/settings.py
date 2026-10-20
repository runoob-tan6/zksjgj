"""应用配置持久化。"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def get_app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


SETTINGS_PATH: Path = get_app_base_dir() / ".Data" / "app_settings.json"


def load_last_project() -> Path | None:
    if not SETTINGS_PATH.exists():
        return None
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    value = data.get("last_project")
    if not value:
        return None
    return Path(value)


def save_last_project(path: Path) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps({"last_project": str(path)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
