from vat.media.video_scanner import VideoInfo
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.media.video_scanner import VideoInfo  # noqa: E402
from vat.ui.playlist_panel import PlaylistPanel  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication | QCoreApplication:
    return QApplication.instance() or QApplication([])


def _videos(*names) -> list[VideoInfo]:
    return [VideoInfo(path=f"/videos/{name}", rel_path=name) for name in names]


def test_annotation_count_shown_when_nonzero(qapp) -> None:
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {}, {"a.mp4": 3})
    assert "(3)" in panel._list.item(0).text()


def test_annotation_count_omitted_when_zero(qapp) -> None:
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {}, {"a.mp4": 0})
    assert "(" not in panel._list.item(0).text()


def test_annotation_count_omitted_when_missing(qapp) -> None:
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {})  # no cut_counts arg at all
    assert "(" not in panel._list.item(0).text()


def test_set_videos_emits_selected_on_first_population(qapp) -> None:
    panel = PlaylistPanel()
    selections = []
    panel.video_selected.connect(selections.append)

    panel.set_videos(_videos("a.mp4", "b.mp4"), {})

    assert selections == ["/videos/a.mp4"]  # row 0 auto-selected


def test_set_videos_does_not_reemit_when_selection_is_unchanged(qapp) -> None:
    # Regression test: refreshing the list (e.g. after Mark Annotated or
    # Add Annotation, which both call refresh_playlist()) with the same
    # video still selected used to re-fire video_selected every time,
    # because setCurrentRow() was called after blockSignals(False) --
    # clear() resets the widget's current row to -1, so "restoring" the
    # same row was still a real (-1 -> N) transition that fired the
    # signal. MainWindow's handler reloads the video unconditionally, so
    # this reset playback to 0 and briefly stalled on every refresh.
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4", "b.mp4"), {})
    panel.select_relative(1)  # now on b.mp4
    selections = []
    panel.video_selected.connect(selections.append)

    # Same videos, same selection (b.mp4) -- e.g. an annotation count changed.
    panel.set_videos(_videos("a.mp4", "b.mp4"), {}, {"b.mp4": 1})

    assert selections == []
    assert panel.current_path() == "/videos/b.mp4"


def test_set_videos_emits_when_previously_selected_video_disappears(qapp) -> None:
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4", "b.mp4"), {})
    panel.select_relative(1)  # now on b.mp4
    selections = []
    panel.video_selected.connect(selections.append)

    panel.set_videos(_videos("a.mp4"), {})  # b.mp4 no longer exists

    assert selections == ["/videos/a.mp4"]


def test_thumbnail_icon_set_when_provided(qapp, tmp_path) -> None:
    thumb_path = tmp_path / "thumb.jpg"
    QPixmap(4, 4).save(str(thumb_path), "JPG")

    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {}, thumbnails={"a.mp4": str(thumb_path)})

    assert panel._list.item(0).icon().isNull() is False


def test_no_thumbnail_icon_when_missing(qapp) -> None:
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {})

    assert panel._list.item(0).icon().isNull() is True


def test_set_thumbnail_updates_icon_for_matching_row(qapp, tmp_path) -> None:
    thumb_path = tmp_path / "thumb.jpg"
    QPixmap(4, 4).save(str(thumb_path), "JPG")

    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4", "b.mp4"), {})
    assert panel._list.item(1).icon().isNull() is True

    panel.set_thumbnail("b.mp4", str(thumb_path))

    assert panel._list.item(1).icon().isNull() is False
    assert panel._list.item(0).icon().isNull() is True  # unrelated row untouched


def test_set_thumbnail_does_not_change_selection(qapp, tmp_path) -> None:
    thumb_path = tmp_path / "thumb.jpg"
    QPixmap(4, 4).save(str(thumb_path), "JPG")

    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4", "b.mp4"), {})
    panel.select_relative(1)
    assert panel.current_path() == "/videos/b.mp4"
    selections = []
    panel.video_selected.connect(selections.append)

    panel.set_thumbnail("a.mp4", str(thumb_path))

    assert panel.current_path() == "/videos/b.mp4"
    assert selections == []  # setting an icon must never re-trigger video_selected


def test_thumbnails_survive_a_set_videos_rebuild(qapp, tmp_path) -> None:
    # set_videos() clear()s and rebuilds every row, dropping their icons.
    # ThumbnailLoader deliberately reports each thumbnail only once per
    # session (re-checking 289 videos on every refresh_playlist() is what
    # made "Mark Annotated" freeze), so the panel has to remember them --
    # otherwise the thumbnails vanished on the next mutating action and
    # never came back.
    thumb_path = tmp_path / "thumb.jpg"
    QPixmap(4, 4).save(str(thumb_path), "JPG")

    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4", "b.mp4"), {})
    panel.set_thumbnail("b.mp4", str(thumb_path))

    panel.set_videos(_videos("a.mp4", "b.mp4"), {"b.mp4": True}, {"b.mp4": 3})

    assert panel._list.item(1).icon().isNull() is False
    assert panel._list.item(0).icon().isNull() is True


def test_thumbnail_cache_drops_videos_that_are_gone(qapp, tmp_path) -> None:
    thumb_path = tmp_path / "thumb.jpg"
    QPixmap(4, 4).save(str(thumb_path), "JPG")

    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {})
    panel.set_thumbnail("a.mp4", str(thumb_path))

    panel.set_videos(_videos("z.mp4"), {})

    assert "a.mp4" not in panel._icons


def test_set_thumbnail_unknown_rel_path_is_a_noop(qapp) -> None:
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {})

    panel.set_thumbnail("does-not-exist.mp4", "/some/path.jpg")  # must not raise


def test_select_relative_steps_through_list(qapp) -> None:
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4", "b.mp4", "c.mp4"), {})
    assert panel.current_path() == "/videos/a.mp4"

    panel.select_relative(1)
    assert panel.current_path() == "/videos/b.mp4"

    panel.select_relative(1)
    assert panel.current_path() == "/videos/c.mp4"


def test_select_relative_clamps_at_bounds(qapp) -> None:
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4", "b.mp4"), {})

    panel.select_relative(-5)  # already at the start, should clamp, not error
    assert panel.current_path() == "/videos/a.mp4"

    panel.select_relative(5)
    assert panel.current_path() == "/videos/b.mp4"
    panel.select_relative(5)  # already at the end
    assert panel.current_path() == "/videos/b.mp4"


def test_select_relative_on_empty_list_is_a_noop(qapp) -> None:
    panel = PlaylistPanel()
    panel.set_videos([], {})
    panel.select_relative(1)  # must not raise
    assert panel.current_path() is None


def test_next_and_previous_path(qapp) -> None:
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4", "b.mp4", "c.mp4"), {})
    assert panel.current_path() == "/videos/a.mp4"
    assert panel.previous_path() is None  # nothing before the first video
    assert panel.next_path() == "/videos/b.mp4"

    panel.select_relative(1)
    assert panel.previous_path() == "/videos/a.mp4"
    assert panel.next_path() == "/videos/c.mp4"

    panel.select_relative(1)
    assert panel.previous_path() == "/videos/b.mp4"
    assert panel.next_path() is None  # nothing after the last video


def test_visible_rows_emitted_after_rebuild_and_on_scroll(qapp) -> None:
    panel = PlaylistPanel()
    panel.resize(300, 120)
    panel.show()  # offscreen platform: gives the list a real viewport size without a display
    seen = []
    panel.visible_rows_changed.connect(lambda rels: seen.append(list(rels)))

    panel.set_videos(_videos(*[f"v{i:02d}.mp4" for i in range(60)]), {})
    qapp.processEvents()

    assert seen, "set_videos() must report the visible range"
    first = seen[-1]
    assert first[0] == "v00.mp4"
    assert len(first) < 60  # only what fits in the viewport, not every row

    panel._list.verticalScrollBar().setValue(panel._list.verticalScrollBar().maximum())
    qapp.processEvents()
    assert seen[-1][-1] == "v59.mp4"
    assert seen[-1] != first
    panel.close()


def test_visible_rows_empty_when_no_videos(qapp) -> None:
    panel = PlaylistPanel()
    assert panel.visible_rel_paths() == []
