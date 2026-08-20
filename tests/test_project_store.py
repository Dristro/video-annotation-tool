import os

import pytest

from vat.errors import DuplicateLabelError, LabelNotFoundError, ProjectAlreadyExistsError, ProjectNotFoundError
from vat.models.label import Label
from vat.project.project_store import ProjectStore


def test_create_writes_project_json(tmp_project_dir, tmp_videos_dir):
    store = ProjectStore.create(tmp_project_dir, tmp_videos_dir)
    assert os.path.exists(os.path.join(tmp_project_dir, "project.json"))
    assert store.config.videos_dir == os.path.abspath(tmp_videos_dir)


def test_create_twice_raises(tmp_project_dir, tmp_videos_dir):
    ProjectStore.create(tmp_project_dir, tmp_videos_dir)
    with pytest.raises(ProjectAlreadyExistsError):
        ProjectStore.create(tmp_project_dir, tmp_videos_dir)


def test_load_missing_raises(tmp_project_dir):
    with pytest.raises(ProjectNotFoundError):
        ProjectStore.load(tmp_project_dir)


def test_load_round_trips_labels(tmp_project_dir, tmp_videos_dir):
    ProjectStore.create(tmp_project_dir, tmp_videos_dir, [Label(name="goal", shortcut="g")])
    loaded = ProjectStore.load(tmp_project_dir)
    assert loaded.config.label_names() == ["goal"]


def test_set_videos_dir_persists(tmp_project_dir, tmp_videos_dir, tmp_path):
    store = ProjectStore.create(tmp_project_dir, tmp_videos_dir)
    new_videos_dir = tmp_path / "other_videos"
    new_videos_dir.mkdir()
    store.set_videos_dir(str(new_videos_dir))

    reloaded = ProjectStore.load(tmp_project_dir)
    assert reloaded.config.videos_dir == os.path.abspath(str(new_videos_dir))


def test_move_project_dir_relocates_files(tmp_project_dir, tmp_videos_dir, tmp_path):
    store = ProjectStore.create(tmp_project_dir, tmp_videos_dir)
    new_dir = str(tmp_path / "moved_project")

    store.move_project_dir(new_dir)

    assert not os.path.exists(tmp_project_dir)
    assert os.path.exists(os.path.join(new_dir, "project.json"))
    assert store.config.project_dir == os.path.abspath(new_dir)


def test_add_label_rejects_duplicate(tmp_project_dir, tmp_videos_dir):
    store = ProjectStore.create(tmp_project_dir, tmp_videos_dir)
    store.add_label("goal", "g")
    with pytest.raises(DuplicateLabelError):
        store.add_label("goal", "x")


def test_rename_label_updates_name_and_shortcut(tmp_project_dir, tmp_videos_dir):
    store = ProjectStore.create(tmp_project_dir, tmp_videos_dir)
    store.add_label("goal", "g")
    store.rename_label("goal", "goal-scored", "s")
    assert store.config.find_label("goal") is None
    renamed = store.config.find_label("goal-scored")
    assert renamed is not None
    assert renamed.shortcut == "s"


def test_add_label_with_description(tmp_project_dir, tmp_videos_dir):
    store = ProjectStore.create(tmp_project_dir, tmp_videos_dir)
    store.add_label("goal", "g", "Ball fully crosses the line")
    label = store.config.find_label("goal")
    assert label.description == "Ball fully crosses the line"


def test_rename_label_updates_description(tmp_project_dir, tmp_videos_dir):
    store = ProjectStore.create(tmp_project_dir, tmp_videos_dir)
    store.add_label("goal", "g", "old description")
    store.rename_label("goal", "goal", new_description="new description")
    assert store.config.find_label("goal").description == "new description"


def test_rename_missing_label_raises(tmp_project_dir, tmp_videos_dir):
    store = ProjectStore.create(tmp_project_dir, tmp_videos_dir)
    with pytest.raises(LabelNotFoundError):
        store.rename_label("missing", "new")


def test_remove_labels(tmp_project_dir, tmp_videos_dir):
    store = ProjectStore.create(tmp_project_dir, tmp_videos_dir)
    store.add_label("goal", "g")
    store.add_label("foul", "f")
    store.remove_labels(["goal"])
    assert store.config.label_names() == ["foul"]
