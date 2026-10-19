from __future__ import annotations

import argparse
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class HashRow:
    sha256: str
    size: int
    path: str

    def to_line(self) -> str:
        return f"{self.sha256}  {self.size}  {self.path}"

    @classmethod
    def from_line(cls, line: str) -> HashRow:
        sha256, size, path = line.rstrip("\r\n").split("  ", maxsplit=2)
        return cls(sha256=sha256, size=int(size), path=path)


def hash_tree(root: Path) -> list[HashRow]:
    files = sorted(item for item in root.rglob("*") if item.is_file())
    return [
        HashRow(
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            size=path.stat().st_size,
            path=path.relative_to(root).as_posix(),
        )
        for path in files
    ]


def read_manifest(path: Path) -> list[HashRow]:
    return [HashRow.from_line(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line]


def write_manifest(path: Path, rows: Sequence[HashRow]) -> None:
    path.write_text("\n".join(row.to_line() for row in rows) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create or verify a deterministic file-tree manifest.")
    parser.add_argument("root", type=Path)
    parser.add_argument("--check", type=Path, metavar="MANIFEST")
    parser.add_argument("--output", type=Path, metavar="MANIFEST")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    actual = hash_tree(args.root)
    if args.check is not None:
        expected = read_manifest(args.check)
        if actual != expected:
            print("File tree differs from the recorded manifest.")
            return 1
        print(f"Verified {len(actual)} files.")
        return 0
    if args.output is not None:
        write_manifest(args.output, actual)
    else:
        print("\n".join(row.to_line() for row in actual))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
