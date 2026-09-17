"""Smoke tests for MainWindow's controller glue.

These deliberately avoid ever selecting a video through the playlist (which
would construct a real MpvPlayer/libmpv instance) -- mpv embedding needs a
real window and isn't meaningfully unit-testable. Instead we exercise the
same controller methods (_on_add_cut, _on_set_annotated, ...) directly,
which is where the actual annotation logic wiring lives.
"""

from vat.project.project import Project
import os

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from vat.project.project import Project  # noqa: E402
from vat.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, tmp_project_dir, tmp_path):
    # Deliberately an *empty* videos directory: MainWindow.__init__ calls
    # refresh_playlist(), which auto-selects row 0 if any video is listed and
    # would immediately construct a real MpvPlayer/libmpv instance. Embedding
    # libmpv into an offscreen (headless test) window segfaults, so these
    # controller tests use a synthetic "a.mp4" rel_path that never needs to
    # actually be loaded through the player.
    empty_videos_dir = tmp_path / "videos"
    empty_videos_dir.mkdir()
    project = Project.create(tmp_project_dir, str(empty_videos_dir))
    project.add_label("goal", "g")
    win = MainWindow(project)
    yield win
    win.close()


def test_main_window_builds_with_labels_loaded(window) -> None:
    assert window.inspector_panel._label_combo.count() == 1


def test_add_cut_via_controller_creates_entry(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    window.inspector_panel.set_pending_in(1.0)
    window.inspector_panel.set_pending_out(2.0)

    window._on_add_cut("goal")

    entry = window.project.get_entry("a.mp4")
    assert entry is not None
    assert len(entry.cuts) == 1
    assert entry.cuts[0].label == "goal"
    # pending in/out should reset after a successful add
    assert window.inspector_panel.pending_in() is None


def test_add_overlapping_cut_prompts_and_is_skipped_when_declined(window, monkeypatch) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    window.inspector_panel.set_pending_in(1.0)
    window.inspector_panel.set_pending_out(5.0)
    window._on_add_cut("goal")

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    window.inspector_panel.set_pending_in(3.0)
    window.inspector_panel.set_pending_out(8.0)
    window._on_add_cut("goal")

    assert len(window.project.get_entry("a.mp4").cuts) == 1


def test_add_overlapping_cut_proceeds_when_confirmed(window, monkeypatch) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    window.inspector_panel.set_pending_in(1.0)
    window.inspector_panel.set_pending_out(5.0)
    window._on_add_cut("goal")

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window.inspector_panel.set_pending_in(3.0)
    window.inspector_panel.set_pending_out(8.0)
    window._on_add_cut("goal")

    assert len(window.project.get_entry("a.mp4").cuts) == 2


def test_mark_annotated_via_controller_updates_playlist(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path

    window._on_set_annotated(True)

    assert window.project.is_annotated("a.mp4") is True


def test_mark_annotated_does_not_reload_currently_selected_video(window) -> None:
    # Regression test: refresh_playlist() (called by _on_set_annotated)
    # used to always re-fire video_selected for whatever video was already
    # selected, via PlaylistPanel.set_videos() re-triggering
    # currentRowChanged on every call -- reloading the video from scratch
    # (resetting playback to 0) and briefly stalling every time. Reported
    # as a real bug.
    open(os.path.join(window.project.config.videos_dir, "a.mp4"), "wb").close()
    load_calls = []
    window.video_panel.load = lambda path: load_calls.append(path)

    window.refresh_playlist()  # initial population: auto-selects + loads a.mp4
    assert len(load_calls) == 1

    window._on_set_annotated(True)

    assert len(load_calls) == 1  # not reloaded


def test_add_cut_does_not_reload_currently_selected_video(window) -> None:
    open(os.path.join(window.project.config.videos_dir, "a.mp4"), "wb").close()
    load_calls = []
    window.video_panel.load = lambda path: load_calls.append(path)
    window.refresh_playlist()
    assert len(load_calls) == 1

    window.inspector_panel.set_pending_in(1.0)
    window.inspector_panel.set_pending_out(2.0)
    window._on_add_cut("goal")

    assert len(load_calls) == 1  # not reloaded


def test_label_shortcut_registered(window) -> None:
    assert "G" in window._label_shortcuts.shortcut_texts()


@pytest.fixture
def scoring_window(qapp, tmp_project_dir, tmp_path):
    empty_videos_dir = tmp_path / "videos"
    empty_videos_dir.mkdir()
    project = Project.create(tmp_project_dir, str(empty_videos_dir))
    project.add_label("goal", "g")
    project.set_scoring_enabled(True)
    project.add_score_definition("Technique", 0, 100, "float")
    project.add_score_definition("Confidence", 1, 5, "int")
    win = MainWindow(project)
    yield win
    win.close()


def test_score_fields_built_from_project_config(scoring_window) -> None:
    assert set(scoring_window.inspector_panel._score_inputs.keys()) == {"Technique", "Confidence"}


def test_add_annotation_blocked_until_scores_valid(scoring_window) -> None:
    win = scoring_window
    win._current_video_path = os.path.join(win.project.config.videos_dir, "a.mp4")
    win.inspector_panel.set_pending_in(1.0)
    win.inspector_panel.set_pending_out(2.0)

    # No scores filled in yet -- must not be addable.
    assert win.inspector_panel._add_cut_btn.isEnabled() is False

    # Out-of-range value -- still blocked.
    win.inspector_panel._score_inputs["Technique"].setText("150")
    win.inspector_panel._score_inputs["Confidence"].setText("3")
    assert win.inspector_panel._add_cut_btn.isEnabled() is False

    # Valid values -- now addable.
    win.inspector_panel._score_inputs["Technique"].setText("87.5")
    assert win.inspector_panel._add_cut_btn.isEnabled() is True

    win._on_add_cut("goal")
    entry = win.project.get_entry("a.mp4")
    assert entry.cuts[0].scores == {"Technique": 87.5, "Confidence": 3}
    # Fields reset after a successful add, ready for the next annotation.
    assert win.inspector_panel._score_inputs["Technique"].text() == ""


def test_cut_flagged_incomplete_after_new_score_added(scoring_window) -> None:
    win = scoring_window
    win._current_video_path = os.path.join(win.project.config.videos_dir, "a.mp4")
    win.inspector_panel.set_pending_in(1.0)
    win.inspector_panel.set_pending_out(2.0)
    win.inspector_panel._score_inputs["Technique"].setText("50")
    win.inspector_panel._score_inputs["Confidence"].setText("3")
    win._on_add_cut("goal")

    win.project.add_score_definition("Difficulty", 0, 10, "float")
    win._refresh_cuts_and_status("a.mp4")

    cut = win.project.get_entry("a.mp4").cuts[0]
    assert win.project.is_cut_complete(cut) is False
    assert win.project.missing_scores(cut) == ["Difficulty"]


def test_selecting_incomplete_cut_prefills_existing_scores_and_blanks_missing(scoring_window) -> None:
    win = scoring_window
    win.project.add_label("foul", "f")
    win._current_video_path = os.path.join(win.project.config.videos_dir, "a.mp4")
    # A cut recorded before "Confidence" existed -- only has Technique.
    cut = win.project.add_cut("a.mp4", 1.0, 2.0, "goal", {"Technique": 50})
    win._refresh_cuts_and_status("a.mp4")

    assert win.inspector_panel._edit_cut_btn.isEnabled() is False  # nothing selected yet

    win.inspector_panel.select_cut_by_id(cut.id)

    assert win.inspector_panel.selected_label_name() == "goal"
    assert win.inspector_panel._score_inputs["Technique"].text() == "50"
    assert win.inspector_panel._score_inputs["Confidence"].text() == ""
    # Missing a required score -- Edit Annotation must stay disabled until filled.
    assert win.inspector_panel._edit_cut_btn.isEnabled() is False
    # Mark In/Out must be cleared by selection, not left over from before.
    assert win.inspector_panel.pending_in() is None
    assert win.inspector_panel.pending_out() is None


def test_edit_annotation_updates_label_and_fills_missing_score(scoring_window) -> None:
    win = scoring_window
    win.project.add_label("foul", "f")
    win._current_video_path = os.path.join(win.project.config.videos_dir, "a.mp4")
    cut = win.project.add_cut("a.mp4", 1.0, 2.0, "goal", {"Technique": 50})
    win._refresh_cuts_and_status("a.mp4")

    win.inspector_panel.select_cut_by_id(cut.id)
    win.inspector_panel._score_inputs["Confidence"].setText("4")
    win.inspector_panel.select_label("foul")
    assert win.inspector_panel._edit_cut_btn.isEnabled() is True

    win._on_edit_cut("foul")

    updated = win.project.get_entry("a.mp4").cuts[0]
    assert updated.label == "foul"
    assert updated.scores == {"Technique": 50.0, "Confidence": 4}
    assert win.project.is_cut_complete(updated) is True
    # Selection (and therefore the visible field values) should survive the
    # refresh triggered by the edit, not reset to nothing.
    assert win.inspector_panel.selected_cut_id() == cut.id


def test_edit_annotation_does_not_affect_add_annotation_state(scoring_window) -> None:
    win = scoring_window
    win._current_video_path = os.path.join(win.project.config.videos_dir, "a.mp4")
    cut = win.project.add_cut("a.mp4", 1.0, 2.0, "goal", {"Technique": 50, "Confidence": 3})
    win._refresh_cuts_and_status("a.mp4")

    win.inspector_panel.set_pending_in(5.0)
    win.inspector_panel.set_pending_out(6.0)
    win.inspector_panel.select_cut_by_id(cut.id)

    # Selecting an existing cut for editing must clear any pending mark
    # in/out, so it can't accidentally be combined with Add Annotation.
    assert win.inspector_panel._add_cut_btn.isEnabled() is False


def test_edit_annotation_without_mark_in_out_keeps_existing_timing(window) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window._refresh_cuts_and_status("a.mp4")
    window.inspector_panel.select_cut_by_id(cut.id)

    window._on_edit_cut("goal")

    updated = window.project.get_entry("a.mp4").cuts[0]
    assert updated.start == 1.0
    assert updated.end == 2.0


def test_edit_annotation_with_mark_in_out_retimes_cut(window) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window._refresh_cuts_and_status("a.mp4")
    window.inspector_panel.select_cut_by_id(cut.id)

    window.inspector_panel.set_pending_in(10.0)
    window.inspector_panel.set_pending_out(20.0)
    window._on_edit_cut("goal")

    updated = window.project.get_entry("a.mp4").cuts[0]
    assert updated.start == 10.0
    assert updated.end == 20.0


def test_edit_annotation_retime_overlap_prompts_and_is_skipped_when_declined(window, monkeypatch) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window.project.add_cut("a.mp4", 1.0, 5.0, "goal")
    cut2 = window.project.add_cut("a.mp4", 10.0, 20.0, "goal")
    window._refresh_cuts_and_status("a.mp4")
    window.inspector_panel.select_cut_by_id(cut2.id)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    window.inspector_panel.set_pending_in(3.0)
    window.inspector_panel.set_pending_out(8.0)
    window._on_edit_cut("goal")

    unchanged = next(c for c in window.project.get_entry("a.mp4").cuts if c.id == cut2.id)
    assert unchanged.start == 10.0
    assert unchanged.end == 20.0


def test_break_continuation_clears_link_when_confirmed(window, monkeypatch) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal", continuation_id="link1", continues_forward=True)
    window._refresh_cuts_and_status("a.mp4")

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window._on_break_continuation(cut.id)

    updated = window.project.get_entry("a.mp4").cuts[0]
    assert updated.continuation_id is None
    assert updated.continues_forward is False


def test_break_continuation_leaves_link_when_declined(window, monkeypatch) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal", continuation_id="link1", continues_forward=True)
    window._refresh_cuts_and_status("a.mp4")

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    window._on_break_continuation(cut.id)

    updated = window.project.get_entry("a.mp4").cuts[0]
    assert updated.continuation_id == "link1"
    assert updated.continues_forward is True


def test_add_cut_includes_justification(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    window.inspector_panel.set_pending_in(1.0)
    window.inspector_panel.set_pending_out(2.0)
    window.inspector_panel._justification_input.setText("clean strike, top corner")

    window._on_add_cut("goal")

    entry = window.project.get_entry("a.mp4")
    assert entry.cuts[0].justification == "clean strike, top corner"
    # cleared after a successful add, like the rest of the pending state
    assert window.inspector_panel.pending_justification() == ""


def test_add_cut_without_justification_defaults_empty(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    window.inspector_panel.set_pending_in(1.0)
    window.inspector_panel.set_pending_out(2.0)

    window._on_add_cut("goal")

    assert window.project.get_entry("a.mp4").cuts[0].justification == ""


def test_edit_annotation_updates_justification(window) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal", justification="first draft")
    window._refresh_cuts_and_status("a.mp4")
    window.inspector_panel.select_cut_by_id(cut.id)

    window.inspector_panel._justification_input.setText("revised reasoning")
    window._on_edit_cut("goal")

    assert window.project.get_entry("a.mp4").cuts[0].justification == "revised reasoning"


def test_edit_annotation_without_touching_justification_keeps_it(window) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal", justification="keep me")
    window._refresh_cuts_and_status("a.mp4")
    window.inspector_panel.select_cut_by_id(cut.id)

    window._on_edit_cut("foul")  # only changing the label

    assert window.project.get_entry("a.mp4").cuts[0].justification == "keep me"


def test_cut_resize_preserves_justification(window) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal", justification="keep me")
    window._refresh_cuts_and_status("a.mp4")

    window._on_cut_resized(cut.id, 5.0, 8.0)

    assert window.project.get_entry("a.mp4").cuts[0].justification == "keep me"


def test_undo_redo_edit_cut_justification(window) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal", justification="original")
    window._refresh_cuts_and_status("a.mp4")
    window.inspector_panel.select_cut_by_id(cut.id)
    window.inspector_panel._justification_input.setText("updated")
    window._on_edit_cut("goal")
    assert window.project.get_entry("a.mp4").cuts[0].justification == "updated"

    window._on_undo()
    assert window.project.get_entry("a.mp4").cuts[0].justification == "original"

    window._on_redo()
    assert window.project.get_entry("a.mp4").cuts[0].justification == "updated"


def test_undo_add_cut_with_justification_then_redo_restores_it(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    window.inspector_panel.set_pending_in(1.0)
    window.inspector_panel.set_pending_out(2.0)
    window.inspector_panel._justification_input.setText("why this cut matters")
    window._on_add_cut("goal")
    window._on_undo()

    window._on_redo()

    assert window.project.get_entry("a.mp4").cuts[0].justification == "why this cut matters"


def test_cut_resized_updates_timing(window) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window._refresh_cuts_and_status("a.mp4")

    window._on_cut_resized(cut.id, 5.0, 8.0)

    updated = window.project.get_entry("a.mp4").cuts[0]
    assert updated.start == 5.0
    assert updated.end == 8.0


def test_cut_resized_noop_when_range_unchanged(window) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window._refresh_cuts_and_status("a.mp4")

    window._on_cut_resized(cut.id, 1.0, 2.0)  # e.g. an edge grab with no actual movement

    assert window._undo_stack.can_undo() is False


def test_cut_resized_overlap_prompts_and_is_skipped_when_declined(window, monkeypatch) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window.project.add_cut("a.mp4", 10.0, 15.0, "goal")
    cut2 = window.project.add_cut("a.mp4", 20.0, 25.0, "goal")
    window._refresh_cuts_and_status("a.mp4")

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    window._on_cut_resized(cut2.id, 12.0, 25.0)

    unchanged = next(c for c in window.project.get_entry("a.mp4").cuts if c.id == cut2.id)
    assert unchanged.start == 20.0


def test_undo_redo_cut_resize(window) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window._refresh_cuts_and_status("a.mp4")

    window._on_cut_resized(cut.id, 5.0, 8.0)
    window._on_undo()
    reverted = window.project.get_entry("a.mp4").cuts[0]
    assert reverted.start == 1.0
    assert reverted.end == 2.0

    window._on_redo()
    reapplied = window.project.get_entry("a.mp4").cuts[0]
    assert reapplied.start == 5.0
    assert reapplied.end == 8.0


def test_undo_add_cut_removes_it(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    window.inspector_panel.set_pending_in(1.0)
    window.inspector_panel.set_pending_out(2.0)
    window._on_add_cut("goal")
    assert len(window.project.get_entry("a.mp4").cuts) == 1

    window._on_undo()

    entry = window.project.get_entry("a.mp4")
    assert entry is None or entry.cuts == []


def test_redo_add_cut_restores_same_id(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    window.inspector_panel.set_pending_in(1.0)
    window.inspector_panel.set_pending_out(2.0)
    window._on_add_cut("goal")
    original_id = window.project.get_entry("a.mp4").cuts[0].id
    window._on_undo()

    window._on_redo()

    cuts = window.project.get_entry("a.mp4").cuts
    assert len(cuts) == 1
    assert cuts[0].id == original_id
    assert cuts[0].label == "goal"


def test_undo_redo_noop_when_stack_empty(window) -> None:
    window._on_undo()  # must not raise
    window._on_redo()  # must not raise


def test_undo_delete_cut_restores_it(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window._refresh_cuts_and_status("a.mp4")
    window.inspector_panel.select_cut_by_id(cut.id)
    window._on_delete_cut(cut.id)  # MainWindow's own handler -- no confirm dialog at this level
    assert window.project.get_entry("a.mp4").cuts == []

    window._on_undo()

    cuts = window.project.get_entry("a.mp4").cuts
    assert len(cuts) == 1
    assert cuts[0].id == cut.id
    assert cuts[0].label == "goal"


def test_redo_delete_cut_removes_it_again(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window._refresh_cuts_and_status("a.mp4")
    window._on_delete_cut(cut.id)
    window._on_undo()
    assert len(window.project.get_entry("a.mp4").cuts) == 1

    window._on_redo()

    assert window.project.get_entry("a.mp4").cuts == []


def test_undo_edit_cut_restores_previous_label_and_scores(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    window.project.add_label("foul", "f")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal", {"Technique": 50})
    window._refresh_cuts_and_status("a.mp4")
    window.inspector_panel.select_cut_by_id(cut.id)
    window._on_edit_cut("foul")
    assert window.project.get_entry("a.mp4").cuts[0].label == "foul"

    window._on_undo()

    updated = window.project.get_entry("a.mp4").cuts[0]
    assert updated.label == "goal"
    assert updated.scores == {"Technique": 50}


def test_redo_edit_cut_reapplies_new_label(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    window.project.add_label("foul", "f")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window._refresh_cuts_and_status("a.mp4")
    window.inspector_panel.select_cut_by_id(cut.id)
    window._on_edit_cut("foul")
    window._on_undo()

    window._on_redo()

    assert window.project.get_entry("a.mp4").cuts[0].label == "foul"


def test_undo_redo_edit_cut_retiming(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window._refresh_cuts_and_status("a.mp4")
    window.inspector_panel.select_cut_by_id(cut.id)
    window.inspector_panel.set_pending_in(10.0)
    window.inspector_panel.set_pending_out(20.0)
    window._on_edit_cut("goal")
    assert window.project.get_entry("a.mp4").cuts[0].start == 10.0

    window._on_undo()
    reverted = window.project.get_entry("a.mp4").cuts[0]
    assert reverted.start == 1.0
    assert reverted.end == 2.0

    window._on_redo()
    reapplied = window.project.get_entry("a.mp4").cuts[0]
    assert reapplied.start == 10.0
    assert reapplied.end == 20.0


def test_undo_after_switching_videos_does_not_crash_and_still_applies(window) -> None:
    # Undoing an action recorded on a video that isn't the current one
    # anymore must still mutate the right data without touching the UI
    # for whatever video happens to be selected now.
    video_a = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_a
    window.inspector_panel.set_pending_in(1.0)
    window.inspector_panel.set_pending_out(2.0)
    window._on_add_cut("goal")

    video_b = os.path.join(window.project.config.videos_dir, "b.mp4")
    window._current_video_path = video_b

    window._on_undo()

    entry = window.project.get_entry("a.mp4")
    assert entry is None or entry.cuts == []


def test_theme_menu_defaults_to_saved_preference(qapp, tmp_project_dir, tmp_path, monkeypatch) -> None:
    from vat import app_settings

    monkeypatch.setattr(app_settings, "_settings_path", lambda: tmp_path / "settings.json")
    app_settings.save_theme("light")

    empty_videos_dir = tmp_path / "videos"
    empty_videos_dir.mkdir()
    project = Project.create(tmp_project_dir, str(empty_videos_dir))
    project.add_label("goal", "g")
    win = MainWindow(project)
    try:
        assert win._theme_actions["light"].isChecked() is True
        assert win._theme_actions["dark"].isChecked() is False
    finally:
        win.close()


def test_set_theme_applies_and_saves(window, monkeypatch, tmp_path) -> None:
    from vat import app_settings

    monkeypatch.setattr(app_settings, "_settings_path", lambda: tmp_path / "settings.json")

    window._on_set_theme("light")

    assert app_settings.load_theme() == "light"
    window_color = QApplication.instance().palette().color(QPalette.ColorRole.Window)
    assert window_color.lightness() >= 128


def test_switch_project_updates_recent_menu(window, monkeypatch, tmp_path) -> None:
    from vat import app_settings

    monkeypatch.setattr(app_settings, "_settings_path", lambda: tmp_path / "settings.json")

    def _new_project(name: str) -> Project:
        proj_dir = tmp_path / f"{name}_project"
        videos_dir = tmp_path / f"{name}_videos"
        videos_dir.mkdir()
        return Project.create(str(proj_dir), str(videos_dir))

    project_a = _new_project("a")
    window._switch_project(project_a)
    # Nothing else has ever been opened yet, and the current project is
    # excluded from its own recent list.
    assert [a.text() for a in window._recent_menu.actions()] == ["(No other recent projects)"]

    project_b = _new_project("b")
    window._switch_project(project_b)
    assert [a.text() for a in window._recent_menu.actions()] == [project_a.config.project_dir]


def test_open_recent_switches_project(window, monkeypatch, tmp_path) -> None:
    from vat import app_settings

    monkeypatch.setattr(app_settings, "_settings_path", lambda: tmp_path / "settings.json")

    def _new_project(name: str) -> Project:
        proj_dir = tmp_path / f"{name}_project"
        videos_dir = tmp_path / f"{name}_videos"
        videos_dir.mkdir()
        return Project.create(str(proj_dir), str(videos_dir))

    project_a = _new_project("a")
    window._switch_project(project_a)
    project_b = _new_project("b")
    window._switch_project(project_b)

    window._on_open_recent(project_a.config.project_dir)

    assert window.project.config.project_dir == project_a.config.project_dir


def test_refresh_playlist_does_not_extract_thumbnails_synchronously(window, monkeypatch) -> None:
    # Regression test: refresh_playlist() used to call get_or_create_thumbnail()
    # (an ffmpeg subprocess) inline for every video, on the main thread. That
    # blocked the UI on every mutating action (Mark Annotated, add/edit/delete
    # a cut, ...) that calls refresh_playlist(), not just on project open --
    # reported as a real hang with the spinning-wait cursor. Thumbnail
    # extraction must only ever happen via ThumbnailLoader's background thread,
    # never inline on the thread that called refresh_playlist().
    import threading

    from vat.playback import thumbnail_loader as thumbnail_loader_module

    calling_threads = []

    def _record_and_return(video_path, cache_dir) -> None:
        calling_threads.append(threading.current_thread())
        return None

    monkeypatch.setattr(thumbnail_loader_module, "get_or_create_thumbnail", _record_and_return)

    open(os.path.join(window.project.config.videos_dir, "a.mp4"), "wb").close()
    window.video_panel.load = lambda path: None

    window.refresh_playlist()

    import time

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not calling_threads:
        QApplication.processEvents()
    assert calling_threads  # extraction did happen (just not on the caller's thread)
    assert threading.main_thread() not in calling_threads


def test_mark_annotated_does_not_re_queue_thumbnail_work(window, monkeypatch) -> None:
    # Regression test for the reported freeze: moving extraction off the
    # main thread wasn't enough on its own. refresh_playlist() runs on
    # nearly every mutating action, and each run used to re-queue every
    # video whose thumbnail wasn't cached yet -- one fresh thread and one
    # fresh ffmpeg process each. Against the real 289-video project that
    # blocked the *main* thread for ~1.5 s per "Mark Annotated" click, and
    # since the extractions themselves were failing, no cache file was ever
    # written to break the cycle.
    import threading
    import time

    from vat.playback import thumbnail_loader as thumbnail_loader_module

    attempts = []
    monkeypatch.setattr(
        thumbnail_loader_module,
        "get_or_create_thumbnail",
        lambda video_path, cache_dir: attempts.append(video_path) or None,
    )

    open(os.path.join(window.project.config.videos_dir, "a.mp4"), "wb").close()
    window.video_panel.load = lambda path: None
    window.refresh_playlist()

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not attempts:
        QApplication.processEvents()
    assert len(attempts) == 1

    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    threads_before = threading.active_count()
    for _ in range(10):
        window._on_set_annotated(True)
        window._on_set_annotated(False)

    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline:
        QApplication.processEvents()
    assert attempts == attempts[:1]  # not one retry across 20 mark/unmark clicks
    assert threading.active_count() <= threads_before


def test_refresh_playlist_includes_annotation_counts(window) -> None:
    # refresh_playlist() needs a real file for its filesystem scan
    # (project.list_videos()) to find -- but populating the playlist also
    # auto-selects row 0, which would normally cascade into
    # _on_video_selected -> video_panel.load() -> a real MpvPlayer. Stub
    # load() out for this test; it only needs to verify that cut counts
    # get computed and threaded through to the playlist display, not that
    # playback actually starts.
    open(os.path.join(window.project.config.videos_dir, "a.mp4"), "wb").close()
    window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window.project.add_cut("a.mp4", 3.0, 4.0, "goal")
    window.video_panel.load = lambda path: None

    window.refresh_playlist()

    assert "(2)" in window.playlist_panel._list.item(0).text()


def test_timeline_double_click_selects_and_seeks(window) -> None:
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window._refresh_cuts_and_status("a.mp4")

    # No real video is loaded (see module docstring), so seek_to() is a
    # no-op on the player side -- this only verifies the *selection* half,
    # which is what drives the inspector's edit fields.
    window._on_timeline_cut_double_clicked(cut.id)

    assert window.inspector_panel.selected_cut_id() == cut.id


def test_navigate_left_right_do_not_raise_without_a_loaded_video(window) -> None:
    # No real player is constructed in these tests -- seek_relative() must
    # be a safe no-op rather than raising when _player is None.
    window._on_navigate_requested("left")
    window._on_navigate_requested("right")


def test_navigate_up_down_steps_playlist(window) -> None:
    # Stub out select_relative rather than populating real video files and
    # calling refresh_playlist(): that would auto-select row 0, which fires
    # _on_video_selected -> video_panel.load() -> a real MpvPlayer. Wiring
    # correctness (right delta, right direction) is all this needs to
    # verify; PlaylistPanel.select_relative()'s own stepping/clamping
    # behavior is covered directly in test_playlist_panel.py.
    calls = []
    window.playlist_panel.select_relative = calls.append

    window._on_navigate_requested("up")
    window._on_navigate_requested("down")

    assert calls == [-1, 1]


@pytest.fixture
def two_video_window(qapp, tmp_project_dir, tmp_path):
    # Two real (empty) files so refresh_playlist()'s filesystem scan finds
    # them and previous_path()/next_path() have something real to step
    # between -- video_panel.load is stubbed so the row-0 auto-selection
    # this triggers can't reach real MpvPlayer construction.
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "a.mp4").write_bytes(b"")
    (videos_dir / "b.mp4").write_bytes(b"")
    project = Project.create(tmp_project_dir, str(videos_dir))
    project.add_label("goal", "g")
    win = MainWindow(project)
    win.video_panel.load = lambda path: None
    win.video_panel._duration = 300.0  # pretend a video is loaded and this long
    win.refresh_playlist()
    yield win
    win.close()


def test_continuation_full_flow_across_two_videos(two_video_window) -> None:
    win = two_video_window

    # -- Video A: mark in near the end, check "continues", add --
    win._on_video_selected(win.playlist_panel.current_path())
    win.inspector_panel.select_label("goal")
    win.inspector_panel.set_pending_in(280.0)
    win.inspector_panel._continues_checkbox.setChecked(True)

    win._on_add_cut("goal")

    cut_a = win.project.get_entry("a.mp4").cuts[0]
    assert cut_a.end == 300.0  # forced to video A's duration, not a marked-out time
    assert cut_a.continues_forward is True
    assert cut_a.continuation_id is not None
    assert "(1)" in win.playlist_panel._list.item(0).text()  # count updated too

    # -- Video B: the banner should offer to complete it --
    win.playlist_panel.select_relative(1)
    win._on_video_selected(win.playlist_panel.current_path())

    assert win.inspector_panel._pending_continuation_cut is not None
    assert win.inspector_panel._pending_continuation_cut.id == cut_a.id

    win.inspector_panel._on_start_continuation()
    assert win.inspector_panel.pending_in() == 0.0
    win.inspector_panel.set_pending_out(75.0)

    win._on_add_cut("goal")

    cut_b = win.project.get_entry("b.mp4").cuts[0]
    assert cut_b.start == 0.0
    assert cut_b.continuation_id == cut_a.continuation_id
    assert cut_b.continues_forward is False

    # Banner should be gone now that it's completed.
    win._refresh_pending_continuation()
    assert win.inspector_panel._pending_continuation_cut is None


def test_continues_checkbox_disabled_on_last_video(two_video_window) -> None:
    win = two_video_window
    win.playlist_panel.select_relative(1)  # move to b.mp4, the last video
    win._on_video_selected(win.playlist_panel.current_path())

    assert win.inspector_panel._continues_checkbox.isEnabled() is False


def test_continues_checkbox_enabled_when_not_last_video(two_video_window) -> None:
    win = two_video_window
    win._on_video_selected(win.playlist_panel.current_path())  # a.mp4, has a next video

    assert win.inspector_panel._continues_checkbox.isEnabled() is True


def test_include_subfolders_menu_action_toggles_project_setting(window) -> None:
    os.mkdir(os.path.join(window.project.config.videos_dir, "sub"))
    open(os.path.join(window.project.config.videos_dir, "sub", "n.mp4"), "wb").close()
    window.video_panel.load = lambda path: None  # keep row-0 auto-selection away from a real player

    assert window._recursive_scan_action.isChecked() is False
    window.refresh_playlist()
    assert window.playlist_panel._rel_paths_by_row == []

    window._recursive_scan_action.setChecked(True)

    assert window.project.config.recursive_scan is True
    assert window.playlist_panel._rel_paths_by_row == ["sub/n.mp4"]
    assert Project.open(window.project.config.project_dir).config.recursive_scan is True


def test_break_continuation_is_undoable(window, monkeypatch) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal", continuation_id="link1", continues_forward=True)
    window._refresh_cuts_and_status("a.mp4")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    window._on_break_continuation(cut.id)
    assert window.project.find_cut("a.mp4", cut.id).continuation_id is None

    window._on_undo()
    restored = window.project.find_cut("a.mp4", cut.id)
    assert (restored.continuation_id, restored.continues_forward) == ("link1", True)
    assert window.inspector_panel.selected_cut_id() == cut.id

    window._on_redo()
    assert window.project.find_cut("a.mp4", cut.id).continuation_id is None


def test_undo_of_a_settings_rename_resyncs_the_inspector(window, monkeypatch) -> None:
    from PySide6.QtWidgets import QDialog

    from vat.ui import label_editor_dialog
    from vat.ui.project_settings_dialog import ProjectSettingsDialog

    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window._refresh_cuts_and_status("a.mp4")

    # Drive the real dialog flow: exec() renames via the labels tab, then returns.
    def _fake_exec(dialog) -> int:
        dialog.labels_widget._table.selectRow(0)
        dialog.labels_widget._on_edit()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ProjectSettingsDialog, "exec", _fake_exec)
    monkeypatch.setattr(label_editor_dialog._LabelFormDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(label_editor_dialog._LabelFormDialog, "values", lambda self: ("score", "", "g"))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    window._on_open_project_settings()
    assert window.inspector_panel._label_combo.itemText(0).startswith("score")
    assert window.project.get_entry("a.mp4").cuts[0].label == "score"

    window._on_undo()
    assert window.project.config.label_names() == ["goal"]
    assert window.inspector_panel._label_combo.itemText(0).startswith("goal")  # listener resynced the combo
    assert window.project.get_entry("a.mp4").cuts[0].label == "goal"
    assert "goal" in window.inspector_panel._cuts_list.item(0).text()


def test_link_continuation_completes_previous_video_front_half_and_is_undoable(two_video_window, monkeypatch) -> None:
    from PySide6.QtWidgets import QDialog

    from vat.ui import continuation_link_dialog

    win = two_video_window
    front = win.project.add_cut("a.mp4", 280.0, 300.0, "goal", continuation_id="chain", continues_forward=True)
    back = win.project.add_cut("b.mp4", 0.0, 5.0, "goal")  # added without linking
    win.playlist_panel.select_relative(1)  # -> b.mp4
    win._on_video_selected(win.playlist_panel.current_path())
    assert win.inspector_panel._pending_continuation_cut is not None  # banner: still pending

    captured = {}

    def _fake_exec(dialog) -> int:
        captured["candidates"] = list(dialog._candidates)
        dialog._candidate_radios[0].setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(continuation_link_dialog.ContinuationLinkDialog, "exec", _fake_exec)
    win.inspector_panel.select_cut_by_id(back.id)
    win._on_link_continuation(back.id)

    assert [c.id for c in captured["candidates"]] == [front.id]
    linked = win.project.find_cut("b.mp4", back.id)
    assert (linked.continuation_id, linked.continues_forward, linked.end) == ("chain", False, 5.0)
    assert win.inspector_panel._pending_continuation_cut is None  # banner gone: completed now

    win._on_undo()
    assert win.project.find_cut("b.mp4", back.id).continuation_id is None
    assert win.inspector_panel._pending_continuation_cut is not None
    win._on_redo()
    assert win.project.find_cut("b.mp4", back.id).continuation_id == "chain"


def test_link_continuation_forward_sets_end_to_video_duration(two_video_window, monkeypatch) -> None:
    from PySide6.QtWidgets import QDialog

    from vat.ui import continuation_link_dialog

    win = two_video_window
    win._on_video_selected(win.playlist_panel.current_path())  # a.mp4, duration stubbed at 300
    cut = win.project.add_cut("a.mp4", 250.0, 260.0, "goal")
    win._refresh_cuts_and_status("a.mp4")

    def _fake_exec(dialog) -> int:
        assert dialog._forward_checkbox.isEnabled()  # b.mp4 exists to continue into
        dialog._forward_checkbox.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(continuation_link_dialog.ContinuationLinkDialog, "exec", _fake_exec)
    win.inspector_panel.select_cut_by_id(cut.id)
    win._on_link_continuation(cut.id)

    linked = win.project.find_cut("a.mp4", cut.id)
    assert linked.continues_forward is True and linked.continuation_id
    assert linked.end == 300.0
    # And b.mp4 now sees it as pending.
    assert win.project.pending_continuation("b.mp4", "a.mp4").id == cut.id

    win._on_undo()
    restored = win.project.find_cut("a.mp4", cut.id)
    assert (restored.continues_forward, restored.continuation_id, restored.end) == (False, None, 260.0)


def test_link_button_visibility_follows_selection(window) -> None:
    window._current_video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    cut = window.project.add_cut("a.mp4", 1.0, 2.0, "goal")
    window._refresh_cuts_and_status("a.mp4")
    panel = window.inspector_panel
    assert panel._link_continuation_btn.isVisibleTo(panel) is False
    panel.select_cut_by_id(cut.id)
    assert panel._link_continuation_btn.isVisibleTo(panel) is True
    assert panel._break_continuation_btn.isVisibleTo(panel) is False  # nothing to break yet
