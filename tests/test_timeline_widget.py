import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.models.cut import Cut  # noqa: E402
from vat.ui.timeline_widget import TimelineWidget  # noqa: E402


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
