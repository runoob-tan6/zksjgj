from pathlib import Path

from borehole.infrastructure.text_io import encode_text, normalize_text_for_compare, read_text_auto


def test_read_text_auto_detects_gbk_and_crlf(tmp_path: Path) -> None:
    target = tmp_path / "ZK1"
    target.write_bytes("中文\r\n★".encode("gbk"))

    result = read_text_auto(target)

    assert result.text == "中文\n★"
    assert result.encoding == "gbk"
    assert result.newline == "\r\n"


def test_missing_text_defaults_to_utf8_and_crlf(tmp_path: Path) -> None:
    result = read_text_auto(tmp_path / "missing")

    assert result.text is None
    assert result.encoding == "utf-8"
    assert result.newline == "\r\n"


def test_compare_and_encode_share_normalized_newlines() -> None:
    assert normalize_text_for_compare("line\r\n★\r\n") == normalize_text_for_compare("line\n★")
    assert encode_text("line\n★", "gbk", "\r\n") == "line\r\n★".encode("gbk")
