import os
from pathlib import Path

import pytest

from borehole.infrastructure.save_transaction import SaveTransaction, SaveTransactionError


def test_commit_replaces_and_deletes_with_backups(tmp_path: Path) -> None:
    first = tmp_path / "ZK1"
    second = tmp_path / "ZK1.-q"
    first.write_bytes(b"old-main")
    second.write_bytes(b"old-test")
    transaction = SaveTransaction()
    transaction.replace(first, b"new-main")
    transaction.delete(second)

    transaction.commit()

    assert first.read_bytes() == b"new-main"
    assert not second.exists()
    backups = list((tmp_path / "tmp").glob("*.bak"))
    assert {backup.read_bytes() for backup in backups} == {b"old-main", b"old-test"}


def test_commit_failure_restores_all_original_files(tmp_path: Path, monkeypatch) -> None:
    first = tmp_path / "ZK1"
    second = tmp_path / "ZK2"
    first.write_bytes(b"old-one")
    second.write_bytes(b"old-two")
    transaction = SaveTransaction()
    transaction.replace(first, b"new-one")
    transaction.replace(second, b"new-two")
    real_replace = os.replace
    calls = 0

    def fail_second_commit(source: str | Path, target: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected replace failure")
        real_replace(source, target)

    monkeypatch.setattr("borehole.infrastructure.save_transaction.os.replace", fail_second_commit)

    with pytest.raises(SaveTransactionError, match="injected replace failure"):
        transaction.commit()

    assert first.read_bytes() == b"old-one"
    assert second.read_bytes() == b"old-two"
    assert not list(tmp_path.glob(".borehole-v3-*.tmp"))


def test_new_file_is_removed_when_later_commit_fails(tmp_path: Path, monkeypatch) -> None:
    new_file = tmp_path / "NEW"
    existing = tmp_path / "ZK1"
    existing.write_bytes(b"old")
    transaction = SaveTransaction()
    transaction.replace(new_file, b"created")
    transaction.replace(existing, b"new")
    real_replace = os.replace
    calls = 0

    def fail_second_commit(source: str | Path, target: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("stop")
        real_replace(source, target)

    monkeypatch.setattr("borehole.infrastructure.save_transaction.os.replace", fail_second_commit)

    with pytest.raises(SaveTransactionError):
        transaction.commit()

    assert not new_file.exists()
    assert existing.read_bytes() == b"old"


def test_successful_commit_clears_operations(tmp_path: Path) -> None:
    target = tmp_path / "ZK1"
    target.write_bytes(b"old")
    transaction = SaveTransaction()
    transaction.replace(target, b"first-save")

    transaction.commit()
    target.write_bytes(b"external-change")
    transaction.commit()

    assert target.read_bytes() == b"external-change"


def test_commit_reports_missing_prepared_temporary_as_transaction_error(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "ZK1"
    transaction = SaveTransaction()
    transaction.replace(target, b"content")
    monkeypatch.setattr(transaction, "_prepare", lambda _operations: None)

    with pytest.raises(SaveTransactionError, match="临时文件"):
        transaction.commit()
