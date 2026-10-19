"""Shared text decoding and newline detection for project files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TextFileData:
    text: str | None
    encoding: str
    newline: str


def normalize_text_for_compare(text: str | None) -> str | None:
    if text is None:
        return None
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def encode_text(text: str, encoding: str, newline: str) -> bytes:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", newline).encode(encoding)


def read_text_auto(path: Path) -> TextFileData:
    if not path.exists():
        return TextFileData(text=None, encoding="utf-8", newline="\r\n")
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\r" if b"\r" in raw else "\n"
    encodings = ["utf-8", "gbk"]
    if os.name == "nt":
        encodings.append("mbcs")
    for encoding in encodings:
        try:
            text = raw.decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
            return TextFileData(text=text, encoding=encoding, newline=newline)
        except UnicodeDecodeError:
            continue
    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    return TextFileData(text=text, encoding="utf-8", newline=newline)
