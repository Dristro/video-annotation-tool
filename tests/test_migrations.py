import json
from pathlib import Path

import pytest

from vat.annotations import annotation_store as annotation_store_module
from vat.annotations.annotation_store import AnnotationStore
from vat.errors import MigrationError, SchemaTooNewError
from vat import migrations
from vat.project import project_store as project_store_module
from vat.migrations import backup_path, upgrade
from vat.project.project_store import ProjectStore


def test_current_version_is_returned_untouched(tmp_path) -> None:
    data = {"schema_version": 1, "x": 1}
    result, changed = upgrade(data, tmp_path / "f.json", 1, {}, "thing")
    assert result is data
    assert changed is False


def test_missing_schema_version_means_version_one(tmp_path) -> None:
    result, changed = upgrade({"x": 1}, tmp_path / "f.json", 1, {}, "thing")
    assert changed is False
    assert result == {"x": 1}


def test_newer_file_is_refused_not_loaded_best_effort(tmp_path) -> None:
    with pytest.raises(SchemaTooNewError, match="version 7"):
        upgrade({"schema_version": 7}, tmp_path / "annotations.json", 1, {}, "annotations file")


def test_steps_are_applied_in_order_and_version_stamped(tmp_path) -> None:
    steps = {
        1: lambda d: {"renamed": d.pop("old"), **d},
        2: lambda d: {**d, "extra": True},
    }
    result, changed = upgrade({"schema_version": 1, "old": 5}, tmp_path / "f.json", 3, steps, "thing")
    assert changed is True
    assert result == {"schema_version": 3, "renamed": 5, "extra": True}


def test_gap_in_registry_raises(tmp_path) -> None:
    with pytest.raises(MigrationError, match="version 2 to 3"):
        upgrade({"schema_version": 1}, tmp_path / "f.json", 3, {1: lambda d: d}, "thing")


def test_original_is_not_mutated(tmp_path) -> None:
    original = {"schema_version": 1, "nested": {"a": 1}}
    upgrade(original, tmp_path / "f.json", 2, {1: lambda d: d["nested"].update(a=2) or d}, "thing")
    assert original["nested"]["a"] == 1


def test_backup_written_once_with_oldest_copy_kept(tmp_path) -> None:
    path = tmp_path / "annotations.json"
    path.write_text(json.dumps({"schema_version": 1, "videos": {"v": 1}}))

    upgrade(json.loads(path.read_text()), path, 2, {1: lambda d: d}, "thing")
    backup = backup_path(path, 1)
    assert backup.exists()
    assert json.loads(backup.read_text())["videos"] == {"v": 1}

    # A second migration attempt from the same version must not clobber
    # the first backup (which is the genuinely original file).
    path.write_text(json.dumps({"schema_version": 1, "videos": {"v": "changed since"}}))
    upgrade(json.loads(path.read_text()), path, 2, {1: lambda d: d}, "thing")
    assert json.loads(backup.read_text())["videos"] == {"v": 1}


def test_annotation_store_migrates_on_load_and_rewrites_once(tmp_path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    path = project_dir / "annotations.json"
    # A synthetic old shape: cuts under "clips" instead of "cuts".
    path.write_text(json.dumps({
        "schema_version": 1,
        "videos": {"a.mp4": {"annotated": True, "clips": [{"start": 1.0, "end": 2.0, "label": "goal"}]}},
    }))

    def _v1_to_v2(data: dict) -> dict:
        for entry in data["videos"].values():
            entry["cuts"] = entry.pop("clips")
        return data

    monkeypatch.setattr(annotation_store_module, "SCHEMA_VERSION", 2)
    monkeypatch.setitem(migrations.ANNOTATION_MIGRATIONS, 1, _v1_to_v2)

    store = AnnotationStore.load(str(project_dir))

    assert store.get_entry("a.mp4").cuts[0].label == "goal"
    on_disk = json.loads(path.read_text())
    assert on_disk["schema_version"] == 2
    assert "cuts" in on_disk["videos"]["a.mp4"]
    assert backup_path(path, 1).exists()


def test_project_store_migrates_on_load(tmp_path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    path = project_dir / "project.json"
    path.write_text(json.dumps({
        "schema_version": 1, "project_dir": str(project_dir), "video_folder": str(tmp_path / "videos"),
    }))

    monkeypatch.setattr(project_store_module, "SCHEMA_VERSION", 2)
    monkeypatch.setitem(migrations.PROJECT_MIGRATIONS, 1, lambda d: {"videos_dir": d.pop("video_folder"), **d})

    store = ProjectStore.load(str(project_dir))

    assert store.config.videos_dir == str(tmp_path / "videos")
    assert json.loads(path.read_text())["schema_version"] == 2
    assert backup_path(path, 1).exists()


def test_project_store_refuses_newer_file(tmp_path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "project.json").write_text(json.dumps({
        "schema_version": 99, "project_dir": str(project_dir), "videos_dir": "/v",
    }))
    with pytest.raises(SchemaTooNewError):
        ProjectStore.load(str(project_dir))


def test_no_backup_or_rewrite_when_already_current(tmp_path) -> None:
    project_dir = tmp_path / "project"
    store = ProjectStore.create(str(project_dir), str(tmp_path))
    before = store.config_path.read_text()
    ProjectStore.load(str(project_dir))
    assert store.config_path.read_text() == before
    assert not list(Path(project_dir).glob("*.bak"))
