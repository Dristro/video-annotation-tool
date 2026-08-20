"""Smoke tests for MainWindow's controller glue.

These deliberately avoid ever selecting a video through the playlist (which
would construct a real MpvPlayer/libmpv instance) -- mpv embedding needs a
real window and isn't meaningfully unit-testable. Instead we exercise the
same controller methods (_on_add_cut, _on_set_annotated, ...) directly,
which is where the actual annotation logic wiring lives.
"""

import os

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

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


def test_main_window_builds_with_labels_loaded(window):
    assert window.inspector_panel._label_combo.count() == 1


def test_add_cut_via_controller_creates_entry(window):
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


def test_mark_annotated_via_controller_updates_playlist(window):
    video_path = os.path.join(window.project.config.videos_dir, "a.mp4")
    window._current_video_path = video_path

    window._on_set_annotated(True)

    assert window.project.is_annotated("a.mp4") is True


def test_label_shortcut_registered(window):
    shortcuts = [s.key().toString() for s in window._label_shortcuts]
    assert "G" in shortcuts
