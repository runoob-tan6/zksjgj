"""Backup creation and bounded retention."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

MAX_BACKUPS_PER_TARGET = 20


def create_backup(target: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    backup = backup_dir / f"{target.name}.{stamp}.{uuid4().hex[:8]}.bak"
    shutil.copy2(target, backup)
    return backup


def prune_backups(backup_dir: Path, target_name: str, keep: int = MAX_BACKUPS_PER_TARGET) -> None:
    if keep < 1 or not backup_dir.exists():
        return
    prefix = f"{target_name}."
    backups = sorted(
        path
        for path in backup_dir.iterdir()
        if path.is_file() and path.name.startswith(prefix) and path.name.endswith(".bak")
    )
    for backup in backups[:-keep]:
        try:
            backup.unlink()
        except OSError:
            continue
