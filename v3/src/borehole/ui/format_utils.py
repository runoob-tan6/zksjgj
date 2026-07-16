"""UI 公共工具函数。"""

from __future__ import annotations


def format_numeric_value(value: str) -> str:
    """编辑完成时，纯整数自动补一位小数。

    "5" → "5.0"，"10" → "10.0"，"3.5" → "3.5"，"abc" → "abc"
    """
    stripped = value.strip()
    if not stripped or "." in stripped:
        return value
    try:
        int(stripped)
        return stripped + ".0"
    except ValueError:
        return value
