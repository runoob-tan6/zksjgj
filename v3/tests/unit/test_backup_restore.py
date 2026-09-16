from pathlib import Path

from borehole.application.backup_restore import list_backups, restore_backups
from borehole.infrastructure.backup_policy import create_backup


def test_list_backups_parses_and_sorts_backup_files(tmp_path: Path) -> None:
    backup_dir = tmp_path / "tmp"
    backup_dir.mkdir()
    backups = {
        "ZK10": "zk10",
        "ZK2": "zk2",
        "ZK1.-h": "zk1-h",
        "ZK1.-c": "zk1-c",
    }
    for name, content in backups.items():
        path = backup_dir / f"{name}.20260915120000000000.00000001.bak"
        path.write_text(content, encoding="utf-8")
    first = backup_dir / "ZK1.-c.20260915110000000000.00000001.bak"
    first.write_text("older", encoding="utf-8")

    entries = list_backups(tmp_path)

    assert [entry.target_name for entry in entries] == ["ZK1.-c", "ZK1.-c", "ZK1.-h", "ZK2", "ZK10"]
    assert entries[0].created_at == "20260915120000000000"


def test_restore_backups_preserves_current_file_as_backup(tmp_path: Path) -> None:
    target = tmp_path / "ZK1"
    target.write_text("before", encoding="utf-8")
    create_backup(target, tmp_path / "tmp")
    target.write_text("after", encoding="utf-8")

    restored = restore_backups(tmp_path, list_backups(tmp_path)[0:1])

    assert restored == [target]
    assert target.read_text(encoding="utf-8") == "before"
    assert any(path.read_text(encoding="utf-8") == "after" for path in (tmp_path / "tmp").glob("*.bak"))
