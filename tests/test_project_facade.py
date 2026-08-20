from vat.project.project import Project


def _make_project(tmp_project_dir, tmp_videos_dir):
    project = Project.create(tmp_project_dir, tmp_videos_dir)
    project.add_label("goal", "g")
    return project


def test_full_annotation_lifecycle(tmp_project_dir, tmp_videos_dir):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    videos = project.list_videos()
    assert [v.rel_path for v in videos] == ["a.mp4", "b.mp4"]

    rel = project.rel_path(videos[0].path)
    assert project.is_annotated(rel) is False

    project.add_cut(rel, 1.0, 2.0, "goal")
    assert project.is_annotated(rel) is False  # cuts alone don't confirm annotation

    project.set_annotated(rel, True)
    assert project.is_annotated(rel) is True


def test_rename_label_propagates_to_annotation_file(tmp_project_dir, tmp_videos_dir):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    videos = project.list_videos()
    rel = project.rel_path(videos[0].path)
    project.add_cut(rel, 1.0, 2.0, "goal")

    project.rename_label("goal", "goal-scored")

    assert project.get_entry(rel).cuts[0].label == "goal-scored"
    assert project.config.find_label("goal-scored") is not None
    assert project.config.find_label("goal") is None


def test_move_project_dir_keeps_annotations_readable(tmp_project_dir, tmp_videos_dir, tmp_path):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    videos = project.list_videos()
    rel = project.rel_path(videos[0].path)
    project.add_cut(rel, 1.0, 2.0, "goal")

    new_dir = str(tmp_path / "moved_project")
    project.move_project_dir(new_dir)

    assert project.config.project_dir == new_dir or project.config.project_dir.endswith("moved_project")
    assert project.get_entry(rel).cuts[0].label == "goal"


def test_change_videos_dir_updates_playlist(tmp_project_dir, tmp_videos_dir, tmp_path):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    other_dir = tmp_path / "other_videos"
    other_dir.mkdir()
    (other_dir / "only.mp4").write_bytes(b"x")

    project.set_videos_dir(str(other_dir))

    assert [v.rel_path for v in project.list_videos()] == ["only.mp4"]
