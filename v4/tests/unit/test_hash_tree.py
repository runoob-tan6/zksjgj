from pathlib import Path

from tools.hash_tree import HashRow, hash_tree


def test_hash_tree_is_stable_and_ignores_directories(tmp_path: Path) -> None:
    (tmp_path / "b").write_bytes(b"b")
    (tmp_path / "folder").mkdir()
    (tmp_path / "folder" / "a").write_bytes(b"a")

    rows = hash_tree(tmp_path)

    assert [row.path for row in rows] == ["b", "folder/a"]
    assert all(len(row.sha256) == 64 for row in rows)
    assert rows[0].size == 1


def test_hash_row_round_trips_manifest_line() -> None:
    row = HashRow("a" * 64, 12, "folder/file.txt")

    assert HashRow.from_line(row.to_line()) == row
