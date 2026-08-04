"""应用配置持久化。"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def get_app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def get_settings_path() -> Path:
    return get_app_base_dir() / ".Data" / "app_settings.json"


def load_last_project() -> Path | None:
    settings_path = get_settings_path()
    if not settings_path.exists():
        return None
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    value = data.get("last_project")
    if not value:
        return None
    return Path(value)


def save_last_project(path: Path) -> bool:
    settings_path = get_settings_path()
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps({"last_project": str(path)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        return False
    return True
