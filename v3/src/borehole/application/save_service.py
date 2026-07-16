"""Plan and commit all project file changes as one transaction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..domain.models import Borehole, ProfileFile, ProjectData
from ..infrastructure.file_writer import (
    build_test_file_lines,
    encode_text_for_path,
    make_file_text,
    render_h_file,
    render_main_file,
    render_pair_file,
    text_would_change,
)
from ..infrastructure.save_transaction import SaveTransaction


@dataclass(frozen=True, slots=True)
class SaveSummary:
    dirty_boreholes: tuple[Borehole, ...]
    deleted_boreholes: tuple[str, ...]
    dirty_profiles: tuple[ProfileFile, ...]
    deleted_profiles: tuple[str, ...]
    dirty_project_files: tuple[ProfileFile, ...]

    @property
    def has_changes(self) -> bool:
        return any(
            (
                self.dirty_boreholes,
                self.deleted_boreholes,
                self.dirty_profiles,
                self.deleted_profiles,
                self.dirty_project_files,
            )
        )


@dataclass(frozen=True, slots=True)
class SaveResult:
    generated: list[Path]
    profile_count: int

    def as_tuple(self) -> tuple[list[Path], int]:
        return self.generated, self.profile_count


class SaveService:
    def __init__(self, project: ProjectData) -> None:
        self.project = project
        self.transaction = SaveTransaction()
        self.generated: list[Path] = []
        self.profile_count = 0

    def summary(self) -> SaveSummary:
        return SaveSummary(
            dirty_boreholes=tuple(self.project.dirty_boreholes()),
            deleted_boreholes=tuple(self.project.deleted_boreholes),
            dirty_profiles=tuple(profile for profile in self.project.profile_files.values() if profile.modified),
            deleted_profiles=tuple(self.project.deleted_profiles),
            dirty_project_files=tuple(
                project_file for project_file in self.project.project_files.values() if project_file.modified
            ),
        )

    def save(self) -> SaveResult:
        summary = self.summary()
        self._plan_boreholes(summary)
        self._plan_profiles(summary)
        self._plan_project_files(summary)
        self.transaction.commit()
        self._mark_saved(summary)
        return SaveResult(generated=self.generated, profile_count=self.profile_count)

    def _replace_text(self, path: Path, content: str) -> bool:
        if not text_would_change(path, content):
            return False
        self.transaction.replace(path, encode_text_for_path(path, content))
        return True

    def _delete(self, path: Path) -> bool:
        if not path.exists():
            return False
        self.transaction.delete(path)
        return True

    def _plan_boreholes(self, summary: SaveSummary) -> None:
        for borehole in self.project.deleted_boreholes.values():
            suffixes = borehole.existing_suffixes or {"main"}
            for suffix in sorted(suffixes):
                path = borehole.folder / (borehole.prefix if suffix == "main" else f"{borehole.prefix}.-{suffix}")
                if self._delete(path):
                    self.generated.append(path)
        for borehole in summary.dirty_boreholes:
            self._plan_borehole(borehole)

    def _plan_borehole(self, borehole: Borehole) -> None:
        folder = borehole.folder
        full_save = borehole.is_new or bool(borehole.old_prefix and borehole.old_prefix != borehole.prefix)
        targets = {
            "main": (folder / borehole.prefix, render_main_file(borehole)),
            "c": (
                folder / f"{borehole.prefix}.-c",
                render_pair_file([(layer.bottom_depth, layer.lithology_code) for layer in borehole.layers]),
            ),
            "b": (
                folder / f"{borehole.prefix}.-b",
                render_pair_file(
                    [(layer.bottom_depth, layer.formation) for layer in borehole.layers], skip_empty_value=True
                ),
            ),
            "d": (
                folder / f"{borehole.prefix}.-d",
                render_pair_file(
                    [(layer.bottom_depth, layer.structure) for layer in borehole.layers], skip_empty_value=True
                ),
            ),
            "g": (
                folder / f"{borehole.prefix}.-g",
                render_pair_file(
                    [(layer.bottom_depth, layer.weathering) for layer in borehole.layers], skip_empty_value=True
                ),
            ),
            "h": (folder / f"{borehole.prefix}.-h", render_h_file(borehole)),
        }
        for suffix in borehole.available_test_suffixes():
            lines = build_test_file_lines(borehole, suffix)
            path = folder / f"{borehole.prefix}.-{suffix}"
            if lines:
                targets[suffix] = (path, make_file_text(lines))
            elif suffix in borehole.dirty_suffixes and suffix in borehole.existing_suffixes and self._delete(path):
                self.generated.append(path)

        suffixes = set(targets) if full_save or not borehole.dirty_suffixes else set(borehole.dirty_suffixes)
        for suffix in sorted(suffixes):
            target = targets.get(suffix)
            if target is not None and self._replace_text(*target):
                self.generated.append(target[0])

        for suffix, content in borehole.extra_files.items():
            path = folder / f"{borehole.prefix}.-{suffix}"
            if self._replace_text(path, content):
                self.generated.append(path)
        for suffix in sorted(borehole.deleted_extra_files):
            path = folder / f"{borehole.prefix}.-{suffix}"
            if self._delete(path):
                self.generated.append(path)
        if borehole.old_prefix and borehole.old_prefix != borehole.prefix:
            for suffix in sorted(borehole.existing_suffixes):
                old_path = folder / (
                    borehole.old_prefix if suffix == "main" else f"{borehole.old_prefix}.-{suffix}"
                )
                self._delete(old_path)

    def _plan_profiles(self, summary: SaveSummary) -> None:
        for profile in summary.dirty_profiles:
            if self._replace_text(profile.path, profile.content):
                self.profile_count += 1
            for suffix, content in profile.extra_files.items():
                if self._replace_text(profile.path.parent / f"{profile.name}.-{suffix}", content):
                    self.profile_count += 1
            for suffix in profile.deleted_extra_files:
                if self._delete(profile.path.parent / f"{profile.name}.-{suffix}"):
                    self.profile_count += 1
        for name, profile in self.project.deleted_profiles.items():
            if self._delete(profile.path):
                self.profile_count += 1
            for suffix in profile.extra_files:
                if self._delete(profile.path.parent / f"{name}.-{suffix}"):
                    self.profile_count += 1

    def _plan_project_files(self, summary: SaveSummary) -> None:
        folder = self.project.folder or Path.cwd()
        for project_file in summary.dirty_project_files:
            for suffix, content in project_file.extra_files.items():
                if self._replace_text(folder / f"{project_file.name}.-{suffix}", content):
                    self.profile_count += 1
            for suffix in project_file.deleted_extra_files:
                if self._delete(folder / f"{project_file.name}.-{suffix}"):
                    self.profile_count += 1

    def _mark_saved(self, summary: SaveSummary) -> None:
        self.project.deleted_boreholes.clear()
        self.project.deleted_profiles.clear()
        for borehole in summary.dirty_boreholes:
            borehole.dirty = False
            borehole.is_new = False
            borehole.dirty_suffixes.clear()
            borehole.deleted_extra_files.clear()
            borehole.old_prefix = None
        for profile in summary.dirty_profiles:
            profile.modified = False
            profile.deleted_extra_files.clear()
        for project_file in summary.dirty_project_files:
            project_file.modified = False
            project_file.deleted_extra_files.clear()
