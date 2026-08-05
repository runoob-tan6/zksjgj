from pathlib import Path

from borehole.application.project_file_operations import ProjectFileOperations
from borehole.domain.models import ProfileFile, ProjectData


def test_profile_rename_keeps_original_disk_name_across_multiple_renames(tmp_path: Path) -> None:
    profile = ProfileFile("H8", tmp_path / "H8", content="main", extra_files={"d0": "extra"})
    project = ProjectData(folder=tmp_path, profile_files={"H8": profile})
    operations = ProjectFileOperations(project)

    operations.rename_profile("H8", "H9")
    renamed = operations.rename_profile("H9", "H10")

    assert renamed is profile
    assert renamed.old_name == "H8"
    assert renamed.path == tmp_path / "H10"
    assert list(project.profile_files) == ["H10"]


def test_profile_copy_owns_independent_extra_file_mapping(tmp_path: Path) -> None:
    source = ProfileFile("H1", tmp_path / "H1", content="main", extra_files={"g": "source"})
    project = ProjectData(folder=tmp_path, profile_files={"H1": source})

    copied = ProjectFileOperations(project).copy_profile("H1", "H2")
    copied.extra_files["g"] = "copy"

    assert copied.modified
    assert copied.path == tmp_path / "H2"
    assert source.extra_files["g"] == "source"


def test_profile_delete_moves_file_to_pending_deletions(tmp_path: Path) -> None:
    profile = ProfileFile("H1", tmp_path / "H1")
    project = ProjectData(folder=tmp_path, profile_files={"H1": profile})

    deleted = ProjectFileOperations(project).delete_profile("H1")

    assert deleted is profile
    assert project.profile_files == {}
    assert project.deleted_profiles == {"H1": profile}
