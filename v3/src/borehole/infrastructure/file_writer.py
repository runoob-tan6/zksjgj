"""文件写入器 - 将领域模型序列化为磁盘文件。"""

from __future__ import annotations

import re
import shutil
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from ..domain.models import END_MARK, BasicLayer, Borehole, ProjectData


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


def backup_existing_file(path: Path, backup_folder: Path | None = None) -> Path | None:
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_dir = backup_folder or path.parent
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{path.name}.{timestamp}.bak"
    shutil.copy2(path, backup)
    return backup


def write_with_backup(path: Path, text: str, backup_folder: Path | None = None) -> bool:
    if not text_would_change(path, text):
        return False
    backup_existing_file(path, backup_folder)
    path.write_bytes(encode_text_for_path(path, text))
    return True


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
        if layer.bottom_depth or layer.description:
            lines.append(f"#{layer.bottom_depth}")
            lines.append(layer.description)
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


def generate_borehole(borehole: Borehole, old_prefix: str | None = None) -> list[Path]:
    generated: list[Path] = []
    folder = borehole.folder
    folder.mkdir(parents=True, exist_ok=True)

    full_save = borehole.is_new or bool(old_prefix and old_prefix != borehole.prefix)
    old_paths_to_remove: list[Path] = []
    if old_prefix and old_prefix != borehole.prefix:
        for suffix in borehole.existing_suffixes:
            old_path = folder / (f"{old_prefix}.-{suffix}" if suffix != "main" else old_prefix)
            if old_path.exists():
                old_paths_to_remove.append(old_path)

    all_targets = {
        "main": (folder / borehole.prefix, render_main_file(borehole)),
        "c": (
            folder / f"{borehole.prefix}.-c",
            render_pair_file([(layer.bottom_depth, layer.lithology_code) for layer in borehole.layers]),
        ),
        "b": (
            folder / f"{borehole.prefix}.-b",
            render_pair_file(
                [(layer.bottom_depth, layer.formation) for layer in borehole.layers], skip_empty_value=True
            ),
        ),
        "d": (
            folder / f"{borehole.prefix}.-d",
            render_pair_file(
                [(layer.bottom_depth, layer.structure) for layer in borehole.layers], skip_empty_value=True
            ),
        ),
        "g": (
            folder / f"{borehole.prefix}.-g",
            render_pair_file(
                [(layer.bottom_depth, layer.weathering) for layer in borehole.layers], skip_empty_value=True
            ),
        ),
        "h": (folder / f"{borehole.prefix}.-h", render_h_file(borehole)),
    }

    for suffix in borehole.available_test_suffixes():
        lines = build_test_file_lines(borehole, suffix)
        if lines:
            all_targets[suffix] = (folder / f"{borehole.prefix}.-{suffix}", make_file_text(lines))
        elif suffix in borehole.dirty_suffixes and suffix in borehole.existing_suffixes:
            path = folder / f"{borehole.prefix}.-{suffix}"
            if path.exists():
                backup_existing_file(path, folder / "tmp")
                path.unlink()
                generated.append(path)

    suffixes_to_save = set(all_targets) if full_save or not borehole.dirty_suffixes else set(borehole.dirty_suffixes)
    for suffix in suffixes_to_save:
        target = all_targets.get(suffix)
        if not target:
            continue
        path, text = target
        if write_with_backup(path, text, folder / "tmp"):
            generated.append(path)

    # 保存额外文件
    for suffix, content in borehole.extra_files.items():
        path = folder / f"{borehole.prefix}.-{suffix}"
        if write_with_backup(path, content, folder / "tmp"):
            generated.append(path)

    # 删除标记为删除的额外文件
    for suffix in borehole.deleted_extra_files:
        path = folder / f"{borehole.prefix}.-{suffix}"
        if path.exists():
            backup_existing_file(path, folder / "tmp")
            path.unlink()
            generated.append(path)
    borehole.deleted_extra_files.clear()

    for old_path in old_paths_to_remove:
        if old_path.exists():
            backup_existing_file(old_path, folder / "tmp")
            old_path.unlink()

    borehole.dirty = False
    borehole.is_new = False
    borehole.dirty_suffixes.clear()
    return generated


def delete_borehole_files(borehole: Borehole) -> list[Path]:
    deleted: list[Path] = []
    suffixes = set(borehole.existing_suffixes)
    if not suffixes:
        suffixes = {"main"}
    for suffix in suffixes:
        path = borehole.folder / (f"{borehole.prefix}.-{suffix}" if suffix != "main" else borehole.prefix)
        if path.exists():
            backup_existing_file(path, borehole.folder / "tmp")
            path.unlink()
            deleted.append(path)
    return deleted


def generate_dirty_boreholes(project: ProjectData) -> list[Path]:
    generated: list[Path] = []
    for borehole in list(project.deleted_boreholes.values()):
        generated.extend(delete_borehole_files(borehole))
    project.deleted_boreholes.clear()
    for borehole in project.dirty_boreholes():
        generated.extend(generate_borehole(borehole, old_prefix=borehole.old_prefix))
        borehole.old_prefix = None
    return generated
