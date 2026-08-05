"""Model operations for profile project files."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.models import ProfileFile, ProjectData


@dataclass(slots=True)
class ProjectFileOperations:
    project: ProjectData

    def create_profile(self, name: str) -> ProfileFile:
        if self.project.folder is None:
            raise ValueError("Project folder is not loaded")
        profile = ProfileFile(name=name, path=self.project.folder / name, modified=True)
        self.project.profile_files[name] = profile
        return profile

    def copy_profile(self, source_name: str, new_name: str) -> ProfileFile:
        source = self.project.profile_files[source_name]
        folder = self.project.folder or source.path.parent
        copied = ProfileFile(
            name=new_name,
            path=folder / new_name,
            content=source.content,
            extra_files=dict(source.extra_files),
            modified=True,
        )
        self.project.profile_files[new_name] = copied
        return copied

    def rename_profile(self, current_name: str, new_name: str) -> ProfileFile:
        profile = self.project.profile_files.pop(current_name)
        if profile.old_name is None:
            profile.old_name = current_name
        profile.name = new_name
        profile.path = (self.project.folder or profile.path.parent) / new_name
        profile.modified = True
        self.project.profile_files[new_name] = profile
        return profile

    def delete_profile(self, name: str) -> ProfileFile:
        profile = self.project.profile_files.pop(name)
        self.project.deleted_profiles[name] = profile
        return profile
