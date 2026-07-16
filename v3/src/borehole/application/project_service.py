"""项目服务 - 项目加载、钻孔管理。"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

from ..domain.enums import KNOWN_SUFFIXES, HoleType
from ..domain.models import Borehole, MainFileData, ProjectData
from ..infrastructure.file_parser import parse_borehole, read_text_file

BOREHOLE_PATTERN: re.Pattern = re.compile(r"^(?:NZK|ZK)[A-Z]*\d+(?:-\d+)?$", re.IGNORECASE)
PROFILE_PATTERN: re.Pattern = re.compile(r"^[HZ]\d+$", re.IGNORECASE)


def is_borehole_prefix(prefix: str) -> bool:
    return bool(BOREHOLE_PATTERN.fullmatch(prefix.strip()))


def is_profile_prefix(prefix: str) -> bool:
    return bool(PROFILE_PATTERN.fullmatch(prefix.strip()))


def hole_type_from_prefix(prefix: str) -> HoleType:
    return HoleType.NZK if prefix.upper().startswith("NZK") else HoleType.ZK


def split_borehole_file(path: Path) -> tuple[str | None, str | None]:
    name = path.name
    if ".-" in name:
        prefix, suffix = name.split(".-", 1)
        if is_borehole_prefix(prefix):
            return prefix, suffix
        return None, None
    if name.startswith("0") or path.suffix:
        return None, None
    if is_borehole_prefix(name):
        return name, "main"
    return None, None


def create_empty_project() -> ProjectData:
    return ProjectData()


def load_project(folder: Path) -> ProjectData:
    project = ProjectData(folder=folder)
    if not folder.exists() or not folder.is_dir():
        project.load_error = f"项目文件夹不存在：{folder}"
        return project

    groups: dict[str, dict[str, Path]] = {}
    profile_groups: dict[str, dict[str, Path]] = {}
    project_groups: dict[str, dict[str, Path]] = {}

    for path in folder.iterdir():
        if not path.is_file():
            continue
        name = path.name
        # 项目级文件（0开头，如 0nzk.-zkt、0yzk.-zkt）
        if name.startswith("0") and ".-" in name:
            prefix, suffix = name.split(".-", 1)
            project_groups.setdefault(prefix, {})[suffix] = path
            continue
        # 剖面文件及其附属数据文件
        if ".-" in name:
            prefix, suffix = name.split(".-", 1)
            if is_profile_prefix(prefix):
                profile_groups.setdefault(prefix, {})[suffix] = path
                continue
        elif is_profile_prefix(name) and "." not in name:
            profile_groups.setdefault(name, {})["main"] = path
            continue

        prefix, suffix = split_borehole_file(path)
        if not prefix or not suffix:
            continue
        groups.setdefault(prefix, {})[suffix] = path

    # 加载项目级文件
    from ..domain.models import ProfileFile
    for prefix, files in project_groups.items():
        pf = ProfileFile(name=prefix, path=files.get("main", folder / prefix))
        for suffix, path in files.items():
            if path.exists():
                pf.extra_files[suffix] = read_text_file(path)
        project.project_files[prefix] = pf

    # 加载剖面文件
    for prefix, files in profile_groups.items():
        profile = ProfileFile(name=prefix, path=files.get("main", folder / prefix))
        if "main" in files and files["main"].exists():
            profile.content = read_text_file(files["main"])
        for suffix, path in files.items():
            if suffix != "main" and path.exists():
                profile.extra_files[suffix] = read_text_file(path)
        project.profile_files[prefix] = profile

    # 加载钻孔文件
    for prefix, files in groups.items():
        normalized_prefix = prefix.upper()
        known_files = {k: v for k, v in files.items() if k == "main" or k in KNOWN_SUFFIXES}
        extra = {k: v for k, v in files.items() if k != "main" and k not in KNOWN_SUFFIXES}
        borehole = parse_borehole(folder, normalized_prefix, {k: v for k, v in known_files.items() if k != "main"})
        for suffix, path in extra.items():
            borehole.extra_files[suffix] = read_text_file(path)
            borehole.existing_suffixes.add(suffix)
        project.boreholes[normalized_prefix] = borehole
    return project


def copy_borehole(project: ProjectData, source: Borehole, new_prefix: str) -> Borehole:
    folder = project.folder or source.folder
    borehole = deepcopy(source)
    borehole.prefix = new_prefix
    borehole.folder = folder
    borehole.hole_type = hole_type_from_prefix(new_prefix)
    borehole.is_new = True
    borehole.dirty = True
    borehole.dirty_suffixes = set()
    borehole.validation_messages = []
    borehole.raw_texts = {}
    borehole.existing_suffixes = set()
    borehole.tests = {}
    lines = borehole.main.normalized_lines()
    lines[0] = new_prefix
    lines[12] = lines[1]
    borehole.main = MainFileData(lines=lines)
    project.boreholes[new_prefix] = borehole
    return borehole


def next_profile_name(project: ProjectData, prefix: str = "H") -> str:
    """生成下一个可用的剖面文件名（H1, H2, ... 或 Z1, Z2, ...）。"""
    prefix = prefix.upper()
    existing = set(project.profile_files.keys())
    number = 1
    while f"{prefix}{number}" in existing:
        number += 1
    return f"{prefix}{number}"


def next_borehole_prefix(project: ProjectData, source_prefix: str) -> str:
    match = re.fullmatch(r"((?:NZK|ZK)[A-Z]*\d+)-(\d+)", source_prefix, re.IGNORECASE)
    if match:
        base = match.group(1)
        number = int(match.group(2)) + 1
        while f"{base}-{number}" in project.boreholes:
            number += 1
        return f"{base}-{number}"

    match = re.fullmatch(r"((?:NZK|ZK)[A-Z]*)(\d+)", source_prefix, re.IGNORECASE)
    if not match:
        return f"{source_prefix}-1"
    base = match.group(1)
    number = int(match.group(2)) + 1
    while f"{base}{number}" in project.boreholes:
        number += 1
    return f"{base}{number}"


def _find_template_borehole(project: ProjectData, hole_type: HoleType) -> Borehole | None:
    same_type = [b for b in project.sorted_boreholes() if b.hole_type == hole_type and not b.is_new]
    if same_type:
        return same_type[0]
    existing = [b for b in project.sorted_boreholes() if not b.is_new]
    return existing[0] if existing else None


def _default_main_lines(prefix: str) -> list[str]:
    lines = [""] * 16
    lines[0] = prefix
    lines[4] = ",90"
    lines[8] = "001"
    lines[10] = "0,0"
    lines[13] = "L"
    lines[14] = ",90"
    return lines


def create_new_borehole(project: ProjectData, prefix: str) -> Borehole:
    folder = project.folder or Path.cwd()
    hole_type = hole_type_from_prefix(prefix)
    template = _find_template_borehole(project, hole_type)
    if template:
        borehole = deepcopy(template)
        borehole.prefix = prefix
        borehole.folder = folder
        borehole.hole_type = hole_type
        borehole.is_new = True
        borehole.dirty = True
        borehole.dirty_suffixes = set()
        borehole.validation_messages = []
        borehole.raw_texts = {}
        borehole.existing_suffixes = set()
        borehole.tests = {}
        borehole.deleted_extra_files = set()
        borehole.old_prefix = None
        lines = borehole.main.normalized_lines()
        lines[0] = prefix
        lines[12] = lines[1]
        borehole.main = MainFileData(lines=lines)
    else:
        borehole = Borehole(prefix=prefix, folder=folder, hole_type=hole_type, is_new=True, dirty=True)
        borehole.main = MainFileData(lines=_default_main_lines(prefix))
    project.boreholes[prefix] = borehole
    return borehole
