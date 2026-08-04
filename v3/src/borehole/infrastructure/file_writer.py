"""文件写入器 - 将领域模型序列化为磁盘文件。"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..domain.models import END_MARK, Borehole


def make_file_text(lines: Iterable[str]) -> str:
    clean = [str(line) for line in lines]
    return "\n".join([*clean, END_MARK])


def read_existing_text(path: Path) -> str | None:
    text, _ = read_existing_text_with_encoding(path)
    return text


def read_existing_text_with_encoding(path: Path) -> tuple[str | None, str]:
    if not path.exists():
        return None, "utf-8"
    for encoding in ("utf-8", "gbk"):
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace"), "utf-8"


def normalize_for_compare(text: str | None) -> str | None:
    if text is None:
        return None
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def _existing_newline(path: Path) -> str:
    if not path.exists():
        return "\r\n"
    raw = path.read_bytes()
    if b"\r\n" in raw:
        return "\r\n"
    if b"\r" in raw:
        return "\r"
    return "\n"


def encode_text_for_path(path: Path, text: str) -> bytes:
    """Encode text using an existing file's encoding and newline convention."""
    _existing, encoding = read_existing_text_with_encoding(path)
    newline = _existing_newline(path)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", newline).encode(encoding)


def text_would_change(path: Path, text: str) -> bool:
    existing_text, _encoding = read_existing_text_with_encoding(path)
    return normalize_for_compare(existing_text) != normalize_for_compare(text)


def render_main_file(borehole: Borehole) -> str:
    lines = borehole.main.normalized_lines()
    lines[12] = lines[1]
    return make_file_text(lines)


def render_pair_file(rows: list[tuple[str, str]], skip_empty_value: bool = False) -> str:
    lines = []
    for depth, value in rows:
        depth = str(depth or "").strip()
        value = str(value or "").strip()
        if skip_empty_value and not value:
            continue
        if depth or value:
            lines.append(f"{depth},{value}")
    return make_file_text(lines)


def render_h_file(borehole: Borehole) -> str:
    lines: list[str] = []
    for layer in borehole.layers:
        depth = str(layer.bottom_depth or "").strip()
        description = str(layer.description or "").strip()
        if depth and description:
            lines.extend((f"#{depth}", description))
    return make_file_text(lines)


def build_test_file_lines(borehole: Borehole, suffix: str) -> list[str]:
    lines = []
    value_limit = 2 if suffix in {"e", "f"} else None
    for record in borehole.tests.get(suffix, []):
        raw_values = record.values[:value_limit] if value_limit else record.values
        values = [str(value or "").strip() for value in raw_values]
        while values and not values[-1]:
            values.pop()
        if any(values):
            lines.append(",".join(values))
    return lines


def render_test_file(borehole: Borehole, suffix: str) -> str:
    return make_file_text(build_test_file_lines(borehole, suffix))
