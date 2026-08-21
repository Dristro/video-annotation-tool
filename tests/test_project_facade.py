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


def test_add_cut_with_scores(tmp_project_dir, tmp_videos_dir):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    project.set_scoring_enabled(True)
    project.add_score_definition("Technique", 0, 100, "float")
    rel = project.rel_path(project.list_videos()[0].path)

    cut = project.add_cut(rel, 1.0, 2.0, "goal", {"Technique": 87.5})

    assert project.get_entry(rel).cuts[0].scores == {"Technique": 87.5}
    assert project.is_cut_complete(cut) is True
    assert project.missing_scores(cut) == []


def test_is_cut_complete_when_scoring_disabled(tmp_project_dir, tmp_videos_dir):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    rel = project.rel_path(project.list_videos()[0].path)
    cut = project.add_cut(rel, 1.0, 2.0, "goal")
    # Scoring never enabled -- a cut with no scores is still "complete".
    assert project.is_cut_complete(cut) is True


def test_cut_flagged_incomplete_when_score_added_after_the_fact(tmp_project_dir, tmp_videos_dir):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    project.set_scoring_enabled(True)
    project.add_score_definition("Technique", 0, 100, "float")
    rel = project.rel_path(project.list_videos()[0].path)
    cut = project.add_cut(rel, 1.0, 2.0, "goal", {"Technique": 50})
    assert project.is_cut_complete(cut) is True

    # A new score is added to the project after this cut already exists --
    # per the chosen design, the old cut is flagged incomplete, not
    # retroactively blocked or auto-filled.
    project.add_score_definition("Confidence", 1, 5, "int")

    assert project.is_cut_complete(cut) is False
    assert project.missing_scores(cut) == ["Confidence"]


def test_rename_score_definition_propagates_to_annotation_file(tmp_project_dir, tmp_videos_dir):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    project.set_scoring_enabled(True)
    project.add_score_definition("Technique", 0, 100, "float")
    rel = project.rel_path(project.list_videos()[0].path)
    project.add_cut(rel, 1.0, 2.0, "goal", {"Technique": 87.5})

    project.rename_score_definition("Technique", "Skill")

    assert project.get_entry(rel).cuts[0].scores == {"Skill": 87.5}
    assert project.config.find_score_definition("Skill") is not None
    assert project.config.find_score_definition("Technique") is None


def test_pending_continuation_none_without_previous_video(tmp_project_dir, tmp_videos_dir):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    assert project.pending_continuation("a.mp4", None) is None


def test_pending_continuation_none_when_previous_video_has_no_cuts(tmp_project_dir, tmp_videos_dir):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    assert project.pending_continuation("b.mp4", "a.mp4") is None


def test_pending_continuation_found_when_previous_cut_continues_forward(tmp_project_dir, tmp_videos_dir):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    front_half = project.add_cut(
        "a.mp4", 280.0, 300.0, "goal", continuation_id="link1", continues_forward=True
    )

    pending = project.pending_continuation("b.mp4", "a.mp4")

    assert pending is not None
    assert pending.id == front_half.id


def test_pending_continuation_not_found_for_ordinary_cut(tmp_project_dir, tmp_videos_dir):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    project.add_cut("a.mp4", 1.0, 2.0, "goal")  # continues_forward=False by default

    assert project.pending_continuation("b.mp4", "a.mp4") is None


def test_pending_continuation_none_once_completed(tmp_project_dir, tmp_videos_dir):
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    project.add_cut("a.mp4", 280.0, 300.0, "goal", continuation_id="link1", continues_forward=True)
    # b.mp4 completes it with a matching continuation_id.
    project.add_cut("b.mp4", 0.0, 75.0, "goal", continuation_id="link1", continues_forward=False)

    assert project.pending_continuation("b.mp4", "a.mp4") is None


def test_pending_continuation_chain_across_three_videos(tmp_project_dir, tmp_videos_dir):
    # A single shared continuation_id propagated through a middle video's
    # cut (both completing the link from A and continuing it into C) must
    # still correctly link each adjacent pair.
    project = _make_project(tmp_project_dir, tmp_videos_dir)
    project.add_cut("a.mp4", 280.0, 300.0, "goal", continuation_id="chain1", continues_forward=True)
    project.add_cut(
        "b.mp4", 0.0, 60.0, "goal", continuation_id="chain1", continues_forward=True
    )  # completes A, continues into the (hypothetical) video after b.mp4

    assert project.pending_continuation("b.mp4", "a.mp4") is None  # already completed by b.mp4's cut
    pending_for_c = project.pending_continuation("c.mp4", "b.mp4")
    assert pending_for_c is not None
    assert pending_for_c.continuation_id == "chain1"
