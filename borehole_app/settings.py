"""钻孔数据编辑工具 - 应用设置模块。

本模块负责应用程序设置的持久化，包括：
- 最近打开的项目路径
- 应用程序配置

设置文件位置：
- 开发模式：项目根目录/.Data/app_settings.json
- 打包模式：可执行文件所在目录/.Data/app_settings.json

典型用法：
    >>> from borehole_app.settings import load_last_project, save_last_project
    >>> last_path = load_last_project()
    >>> if last_path:
    ...     print(f"上次打开的项目：{last_path}")
    >>> save_last_project(Path("/data/project"))
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def get_app_base_dir() -> Path:
    """获取应用程序基础目录。

    开发模式下返回项目根目录，打包模式下返回可执行文件所在目录。

    Returns:
        应用程序基础目录路径

    Example:
        >>> base_dir = get_app_base_dir()
        >>> print(base_dir)
        '/path/to/project'
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


SETTINGS_PATH: Path = get_app_base_dir() / ".Data" / "app_settings.json"
"""设置文件路径。"""


def load_last_project() -> Path | None:
    """加载上次打开的项目路径。

    Returns:
        上次打开的项目路径，不存在时返回None

    Example:
        >>> last_path = load_last_project()
        >>> if last_path:
        ...     print(f"上次打开的项目：{last_path}")
        ... else:
        ...     print("没有历史项目")
    """
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
    """保存上次打开的项目路径。

    Args:
        path: 项目路径

    Example:
        >>> save_last_project(Path("/data/project"))
    """
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps({"last_project": str(path)}, ensure_ascii=False, indent=2), encoding="utf-8")
