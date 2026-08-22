import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.media.video_scanner import VideoInfo  # noqa: E402
from vat.ui.playlist_panel import PlaylistPanel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _videos(*names):
    return [VideoInfo(path=f"/videos/{name}", rel_path=name) for name in names]


def test_annotation_count_shown_when_nonzero(qapp):
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {}, {"a.mp4": 3})
    assert "(3)" in panel._list.item(0).text()


def test_annotation_count_omitted_when_zero(qapp):
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {}, {"a.mp4": 0})
    assert "(" not in panel._list.item(0).text()


def test_annotation_count_omitted_when_missing(qapp):
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {})  # no cut_counts arg at all
    assert "(" not in panel._list.item(0).text()


def test_thumbnail_icon_set_when_provided(qapp, tmp_path):
    thumb_path = tmp_path / "thumb.jpg"
    QPixmap(4, 4).save(str(thumb_path), "JPG")

    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {}, thumbnails={"a.mp4": str(thumb_path)})

    assert panel._list.item(0).icon().isNull() is False


def test_no_thumbnail_icon_when_missing(qapp):
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {})

    assert panel._list.item(0).icon().isNull() is True


def test_set_thumbnail_updates_icon_for_matching_row(qapp, tmp_path):
    thumb_path = tmp_path / "thumb.jpg"
    QPixmap(4, 4).save(str(thumb_path), "JPG")

    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4", "b.mp4"), {})
    assert panel._list.item(1).icon().isNull() is True

    panel.set_thumbnail("b.mp4", str(thumb_path))

    assert panel._list.item(1).icon().isNull() is False
    assert panel._list.item(0).icon().isNull() is True  # unrelated row untouched


def test_set_thumbnail_does_not_change_selection(qapp, tmp_path):
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


def test_set_thumbnail_unknown_rel_path_is_a_noop(qapp):
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4"), {})

    panel.set_thumbnail("does-not-exist.mp4", "/some/path.jpg")  # must not raise


def test_select_relative_steps_through_list(qapp):
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4", "b.mp4", "c.mp4"), {})
    assert panel.current_path() == "/videos/a.mp4"

    panel.select_relative(1)
    assert panel.current_path() == "/videos/b.mp4"

    panel.select_relative(1)
    assert panel.current_path() == "/videos/c.mp4"


def test_select_relative_clamps_at_bounds(qapp):
    panel = PlaylistPanel()
    panel.set_videos(_videos("a.mp4", "b.mp4"), {})

    panel.select_relative(-5)  # already at the start, should clamp, not error
    assert panel.current_path() == "/videos/a.mp4"

    panel.select_relative(5)
    assert panel.current_path() == "/videos/b.mp4"
    panel.select_relative(5)  # already at the end
    assert panel.current_path() == "/videos/b.mp4"


def test_select_relative_on_empty_list_is_a_noop(qapp):
    panel = PlaylistPanel()
    panel.set_videos([], {})
    panel.select_relative(1)  # must not raise
    assert panel.current_path() is None


def test_next_and_previous_path(qapp):
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
