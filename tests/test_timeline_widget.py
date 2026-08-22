import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QHelpEvent, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolTip  # noqa: E402

from vat.models.cut import Cut  # noqa: E402
from vat.ui.timeline_widget import TimelineWidget, _continuation_tag  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _mouse_event(event_type, x, button=Qt.MouseButton.LeftButton, buttons=None):
    return QMouseEvent(
        event_type, QPointF(x, 20), button,
        buttons if buttons is not None else button,
        Qt.KeyboardModifier.NoModifier,
    )


@pytest.fixture
def timeline(qapp):
    tl = TimelineWidget()
    tl.resize(400, 60)
    tl.set_duration(10.0)
    return tl


def test_drag_scrub_emits_seek_continuously(timeline):
    seeks = []
    timeline.seek_requested.connect(seeks.append)

    timeline.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, 40))
    timeline.mouseMoveEvent(_mouse_event(QEvent.Type.MouseMove, 100, button=Qt.MouseButton.NoButton))
    timeline.mouseMoveEvent(_mouse_event(QEvent.Type.MouseMove, 200, button=Qt.MouseButton.NoButton))
    timeline.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, 200))

    assert len(seeks) == 3  # press + two moves
    assert seeks == sorted(seeks)  # dragging right -> monotonically increasing time


def test_dragging_flag_set_and_cleared(timeline):
    assert timeline._dragging is False
    timeline.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, 40))
    assert timeline._dragging is True
    timeline.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, 40))
    assert timeline._dragging is False


def test_set_position_ignored_while_dragging(timeline):
    timeline.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, 40))
    position_during_drag = timeline._position

    timeline.set_position(9.9)  # simulates an async mpv position update

    assert timeline._position == position_during_drag  # unaffected by the external update
    timeline.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, 40))


def test_set_position_honored_after_drag_ends(timeline):
    timeline.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, 40))
    timeline.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, 40))

    timeline.set_position(9.9)

    assert timeline._position == 9.9


def test_double_click_on_cut_emits_cut_double_clicked(timeline):
    cut = Cut(start=1.0, end=2.0, label="goal")
    timeline.set_cuts([cut])
    double_clicked = []
    timeline.cut_double_clicked.connect(double_clicked.append)

    x = timeline._x_for_time(1.5)  # inside the cut's region
    timeline.mouseDoubleClickEvent(_mouse_event(QEvent.Type.MouseButtonDblClick, x))

    assert double_clicked == [cut.id]


def test_double_click_on_empty_track_does_not_emit(timeline):
    cut = Cut(start=1.0, end=2.0, label="goal")
    timeline.set_cuts([cut])
    double_clicked = []
    timeline.cut_double_clicked.connect(double_clicked.append)

    x = timeline._x_for_time(8.0)  # nowhere near the cut
    timeline.mouseDoubleClickEvent(_mouse_event(QEvent.Type.MouseButtonDblClick, x))

    assert double_clicked == []


def test_single_click_on_cut_selects_it(timeline):
    cut = Cut(start=1.0, end=2.0, label="goal")
    timeline.set_cuts([cut])
    selected = []
    timeline.cut_selected.connect(selected.append)

    x = timeline._x_for_time(1.5)
    timeline.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, x))

    assert selected == [cut.id]


def test_hover_over_cut_shows_tooltip_with_scores(timeline, monkeypatch):
    cut = Cut(start=1.0, end=2.0, label="goal", scores={"Technique": 87.5})
    timeline.set_cuts([cut])

    shown = []
    monkeypatch.setattr(QToolTip, "showText", lambda pos, text, widget: shown.append(text))

    x = int(timeline._x_for_time(1.5))
    help_event = QHelpEvent(QEvent.Type.ToolTip, QPoint(x, 20), QPoint(x, 20))
    timeline.event(help_event)

    assert len(shown) == 1
    assert "goal" in shown[0]
    assert "Technique: 87.5" in shown[0]


def test_hover_over_cut_shows_justification_in_tooltip(timeline, monkeypatch):
    cut = Cut(start=1.0, end=2.0, label="goal", justification="clean strike, top corner")
    timeline.set_cuts([cut])

    shown = []
    monkeypatch.setattr(QToolTip, "showText", lambda pos, text, widget: shown.append(text))

    x = int(timeline._x_for_time(1.5))
    help_event = QHelpEvent(QEvent.Type.ToolTip, QPoint(x, 20), QPoint(x, 20))
    timeline.event(help_event)

    assert "clean strike, top corner" in shown[0]


def test_hover_away_from_any_cut_does_not_show_tooltip(timeline, monkeypatch):
    cut = Cut(start=1.0, end=2.0, label="goal")
    timeline.set_cuts([cut])

    shown = []
    monkeypatch.setattr(QToolTip, "showText", lambda pos, text, widget: shown.append(text))

    x = int(timeline._x_for_time(8.0))  # nowhere near the cut
    help_event = QHelpEvent(QEvent.Type.ToolTip, QPoint(x, 20), QPoint(x, 20))
    timeline.event(help_event)

    assert shown == []


def test_press_near_start_edge_begins_resize_not_scrub(timeline):
    cut = Cut(start=2.0, end=4.0, label="goal")
    timeline.set_cuts([cut])
    seeks = []
    timeline.seek_requested.connect(seeks.append)

    start_x = timeline._x_for_time(2.0)
    timeline.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, start_x))

    assert timeline._resize_cut_id == cut.id
    assert timeline._resize_edge == "start"
    assert timeline._dragging is False
    assert seeks == []  # a resize-grab must not also scrub/seek


def test_press_away_from_edges_scrubs_as_before(timeline):
    cut = Cut(start=2.0, end=4.0, label="goal")
    timeline.set_cuts([cut])

    far_x = timeline._x_for_time(8.0)
    timeline.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, far_x))

    assert timeline._resize_cut_id is None
    assert timeline._dragging is True


def test_drag_start_edge_updates_live_resize_and_clamps_to_min_length(timeline):
    cut = Cut(start=2.0, end=4.0, label="goal")
    timeline.set_cuts([cut])
    start_x = timeline._x_for_time(2.0)
    timeline.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, start_x))

    # Drag the start edge to 3s -- still valid (< end).
    timeline.mouseMoveEvent(
        _mouse_event(QEvent.Type.MouseMove, timeline._x_for_time(3.0), button=Qt.MouseButton.NoButton)
    )
    assert timeline._live_resize[0] == pytest.approx(3.0, abs=0.05)

    # Drag past the end edge -- must clamp instead of crossing it.
    timeline.mouseMoveEvent(
        _mouse_event(QEvent.Type.MouseMove, timeline._x_for_time(9.0), button=Qt.MouseButton.NoButton)
    )
    new_start, new_end = timeline._live_resize
    assert new_end == 4.0
    assert new_start < new_end


def test_drag_end_edge_clamps_to_duration(timeline):
    cut = Cut(start=2.0, end=4.0, label="goal")
    timeline.set_cuts([cut])
    end_x = timeline._x_for_time(4.0)
    timeline.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, end_x))
    assert timeline._resize_edge == "end"

    timeline.mouseMoveEvent(
        _mouse_event(QEvent.Type.MouseMove, timeline._x_for_time(20.0), button=Qt.MouseButton.NoButton)
    )

    new_start, new_end = timeline._live_resize
    assert new_end <= timeline._duration


def test_release_after_resize_emits_cut_resized_and_clears_state(timeline):
    cut = Cut(start=2.0, end=4.0, label="goal")
    timeline.set_cuts([cut])
    end_x = timeline._x_for_time(4.0)
    timeline.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, end_x))
    timeline.mouseMoveEvent(
        _mouse_event(QEvent.Type.MouseMove, timeline._x_for_time(6.0), button=Qt.MouseButton.NoButton)
    )

    resized = []
    timeline.cut_resized.connect(lambda *args: resized.append(args))
    timeline.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, timeline._x_for_time(6.0)))

    assert len(resized) == 1
    emitted_id, new_start, new_end = resized[0]
    assert emitted_id == cut.id
    assert new_start == 2.0
    assert new_end == pytest.approx(6.0, abs=0.05)
    assert timeline._resize_cut_id is None
    assert timeline._live_resize is None


def test_edge_grab_also_selects_the_cut(timeline):
    cut = Cut(start=2.0, end=4.0, label="goal")
    timeline.set_cuts([cut])
    selected = []
    timeline.cut_selected.connect(selected.append)

    timeline.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, timeline._x_for_time(2.0)))

    assert selected == [cut.id]


def test_paints_without_error_with_waveform(timeline):
    timeline.set_waveform([0.1, 0.5, 1.0, 0.2] * 20)
    timeline.show()

    timeline.repaint()  # must not raise


def test_paints_without_error_with_no_waveform(timeline):
    timeline.set_waveform(None)
    timeline.show()

    timeline.repaint()  # must not raise


def test_set_waveform_stores_peaks(timeline):
    peaks = [0.1, 0.2, 0.3]
    timeline.set_waveform(peaks)

    assert timeline._waveform == peaks


def test_continuation_tag_empty_for_ordinary_cut():
    assert _continuation_tag(Cut(start=0.0, end=1.0)) == ""


def test_continuation_tag_derived_from_continuation_id():
    cut = Cut(start=0.0, end=1.0, continuation_id="abcdef123", continues_forward=True)
    assert _continuation_tag(cut) == " #abcd"


def test_continuation_tag_matches_for_linked_pair():
    front = Cut(start=8.0, end=10.0, continuation_id="shared123", continues_forward=True)
    back = Cut(start=0.0, end=2.0, continuation_id="shared123", continues_forward=False)
    assert _continuation_tag(front) == _continuation_tag(back)


def test_hover_over_continuation_cut_tooltip_includes_tag(timeline, monkeypatch):
    cut = Cut(start=1.0, end=2.0, label="goal", continuation_id="abcdef123", continues_forward=True)
    timeline.set_cuts([cut])

    shown = []
    monkeypatch.setattr(QToolTip, "showText", lambda pos, text, widget: shown.append(text))

    x = int(timeline._x_for_time(1.5))
    help_event = QHelpEvent(QEvent.Type.ToolTip, QPoint(x, 20), QPoint(x, 20))
    timeline.event(help_event)

    assert "continuation #abcd" in shown[0]


def test_paints_without_error_for_continuation_cuts(timeline):
    front_half = Cut(start=8.0, end=10.0, label="goal", continuation_id="link1", continues_forward=True)
    back_half = Cut(start=0.0, end=2.0, label="goal", continuation_id="link1", continues_forward=False)
    timeline.set_cuts([front_half, back_half])
    timeline.show()  # a real paintEvent only fires once the widget is shown

    timeline.repaint()  # must not raise
