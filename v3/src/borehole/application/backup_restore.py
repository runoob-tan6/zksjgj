"""List and restore persistent project-file backups."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..domain.sorting import natural_identifier_key
from ..infrastructure.backup_policy import create_backup, prune_backups


@dataclass(frozen=True, slots=True)
class BackupEntry:
    backup: Path
    target_name: str
    created_at: str


def list_backups(project_folder: Path) -> list[BackupEntry]:
    backup_dir = project_folder / "tmp"
    if not backup_dir.is_dir():
        return []
    entries: list[BackupEntry] = []
    for path in backup_dir.glob("*.bak"):
        parts = path.name.rsplit(".", 3)
        if len(parts) != 4 or len(parts[1]) != 20:
            continue
        target_name, created_at, _unique, _extension = parts
        entries.append(BackupEntry(path, target_name, created_at))
    return sorted(entries, key=_backup_sort_key)


def _backup_sort_key(entry: BackupEntry) -> tuple[tuple[int, str, int, int, int, str], str, int, str]:
    base_name, separator, suffix = entry.target_name.partition(".-")
    return natural_identifier_key(base_name), suffix if separator else "", -int(entry.created_at), entry.backup.name


def restore_backups(project_folder: Path, entries: list[BackupEntry]) -> list[Path]:
    """Restore selected backups, preserving the current files as new backups."""
    restored: list[Path] = []
    for entry in entries:
        target = project_folder / entry.target_name
        if target.exists():
            create_backup(target, project_folder / "tmp")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry.backup, target)
        prune_backups(project_folder / "tmp", target.name)
        restored.append(target)
    return restored
