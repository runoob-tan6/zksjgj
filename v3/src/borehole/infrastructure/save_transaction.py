"""Atomic multi-file save transaction with persistent backups and rollback."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4


class SaveTransactionError(RuntimeError):
    """Raised when a save transaction cannot be committed or rolled back."""


@dataclass(slots=True)
class _Operation:
    target: Path
    content: bytes | None
    temporary: Path | None = None
    backup: Path | None = None
    existed: bool = False
    applied: bool = False


class SaveTransaction:
    def __init__(self) -> None:
        self._operations: dict[Path, _Operation] = {}

    def replace(self, target: Path, content: bytes) -> None:
        self._operations[target] = _Operation(target=target, content=content)

    def delete(self, target: Path) -> None:
        self._operations[target] = _Operation(target=target, content=None)

    def commit(self) -> None:
        operations = list(self._operations.values())
        try:
            self._prepare(operations)
            for operation in operations:
                if operation.content is None:
                    if operation.target.exists():
                        operation.target.unlink()
                        operation.applied = True
                    continue
                assert operation.temporary is not None
                os.replace(operation.temporary, operation.target)
                operation.temporary = None
                operation.applied = True
        except Exception as error:
            rollback_errors = self._rollback(operations)
            detail = f"保存事务失败：{error}"
            if rollback_errors:
                detail += "；回滚失败：" + "；".join(rollback_errors)
            raise SaveTransactionError(detail) from error
        finally:
            self._cleanup_temporaries(operations)

    def _prepare(self, operations: list[_Operation]) -> None:
        stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        for operation in operations:
            operation.target.parent.mkdir(parents=True, exist_ok=True)
            operation.existed = operation.target.exists()
            if operation.content is not None:
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=".borehole-v3-", suffix=".tmp", dir=operation.target.parent
                )
                os.close(descriptor)
                operation.temporary = Path(temporary_name)
                operation.temporary.write_bytes(operation.content)
            if operation.existed:
                backup_dir = operation.target.parent / "tmp"
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_name = f"{operation.target.name}.{stamp}.{uuid4().hex[:8]}.bak"
                operation.backup = backup_dir / backup_name
                shutil.copy2(operation.target, operation.backup)

    @staticmethod
    def _rollback(operations: list[_Operation]) -> list[str]:
        errors: list[str] = []
        for operation in reversed(operations):
            if not operation.applied:
                continue
            try:
                if operation.existed and operation.backup is not None:
                    shutil.copy2(operation.backup, operation.target)
                elif operation.target.exists():
                    operation.target.unlink()
            except Exception as error:
                errors.append(f"{operation.target}: {error}")
        return errors

    @staticmethod
    def _cleanup_temporaries(operations: list[_Operation]) -> None:
        for operation in operations:
            temporary = operation.temporary
            if temporary is not None and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass
