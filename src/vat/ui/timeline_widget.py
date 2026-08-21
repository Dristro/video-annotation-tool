from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from vat.models.cut import Cut
from vat.ui.video_panel import format_time
from vat.utils.colors import color_for_label, contrasting_text_color

TRACK_HEIGHT = 28
TRACK_MARGIN_TOP = 12


def _continuation_tag(cut: Cut) -> str:
    """Short, stable text tag (first 4 hex chars of continuation_id) so
    two cuts that link to each other -- shown on different videos'
    timelines, possibly among several other continuing cuts -- can be
    told apart at a glance instead of only by matching label/timing by
    eye (BACKLOG.md). Empty for a cut with no continuation link at all.
    """
    if not cut.continuation_id:
        return ""
    return f" #{cut.continuation_id[:4]}"


class TimelineWidget(QWidget):
    """Bottom panel: a duration-scaled bar showing existing cuts as colored
    regions, with a playhead line.

    This is the sole scrubbing control (the video panel's own position
    slider was removed in favor of it) -- press-and-drag anywhere to scrub
    live, click on a cut to select it (loads it for editing in the
    inspector), double-click a cut to select it *and* seek playback to its
    start.
    """

    seek_requested = Signal(float)  # seconds
    cut_selected = Signal(str)  # cut id
    cut_double_clicked = Signal(str)  # cut id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(TRACK_MARGIN_TOP + TRACK_HEIGHT + 12)
        self._duration: float = 0.0
        self._position: float = 0.0
        self._cuts: list[Cut] = []
        # While the user is dragging, the position shown must track the
        # drag itself, not whatever mpv's async position observer reports
        # in the meantime (which lags slightly behind a seek and would
        # otherwise make the playhead jitter/fight the mouse).
        self._dragging = False

    def set_duration(self, seconds: float) -> None:
        self._duration = max(0.0, seconds)
        self.update()

    def set_position(self, seconds: float) -> None:
        if self._dragging:
            return
        self._position = max(0.0, seconds)
        self.update()

    def set_cuts(self, cuts: list[Cut]) -> None:
        self._cuts = list(cuts)
        self.update()

    def _x_for_time(self, seconds: float) -> float:
        if self._duration <= 0:
            return 0.0
        usable_width = max(1, self.width() - 4)
        return 2 + (seconds / self._duration) * usable_width

    def _time_for_x(self, x: float) -> float:
        if self._duration <= 0:
            return 0.0
        usable_width = max(1, self.width() - 4)
        fraction = min(max((x - 2) / usable_width, 0.0), 1.0)
        return fraction * self._duration

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_rect = QRectF(2, TRACK_MARGIN_TOP, max(1, self.width() - 4), TRACK_HEIGHT)
        painter.setPen(QPen(Qt.GlobalColor.darkGray))
        painter.setBrush(Qt.GlobalColor.lightGray)
        painter.drawRoundedRect(track_rect, 3, 3)

        for cut in self._cuts:
            start_x = self._x_for_time(cut.start)
            end_x = self._x_for_time(cut.end)
            rect = QRectF(start_x, TRACK_MARGIN_TOP, max(2.0, end_x - start_x), TRACK_HEIGHT)
            color = color_for_label(cut.label)
            painter.setBrush(color)
            painter.setPen(QPen(color.darker(150)))
            painter.drawRoundedRect(rect, 2, 2)
            if cut.label or cut.continuation_id:
                # "->" marks the front half (continues into the next
                # video), "<-" marks the back half (continued from the
                # previous one) -- see Cut.continuation_id's docstring.
                prefix = "← " if cut.continuation_id and not cut.continues_forward else ""
                suffix = " →" if cut.continues_forward else ""
                painter.setPen(QPen(contrasting_text_color(color)))
                painter.drawText(
                    rect.adjusted(3, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter,
                    f"{prefix}{cut.label}{suffix}{_continuation_tag(cut)}",
                )

        if self._duration > 0:
            playhead_x = self._x_for_time(self._position)
            painter.setPen(QPen(Qt.GlobalColor.red, 2))
            painter.drawLine(int(playhead_x), 0, int(playhead_x), self.height())

    def event(self, event) -> bool:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.ToolTip:
            cut = self._cut_at(event.pos().x())
            if cut is not None:
                QToolTip.showText(event.globalPos(), self._tooltip_text(cut), self)
            else:
                QToolTip.hideText()
            return True
        return super().event(event)

    def _tooltip_text(self, cut: Cut) -> str:
        # Score values aren't shown on the cut rectangles themselves (no
        # room) -- only in the inspector's cuts list text. A hover tooltip
        # surfaces them here too, per BACKLOG.md, without needing more
        # on-timeline real estate.
        lines = [f"{format_time(cut.start)} – {format_time(cut.end)}"]
        if cut.label:
            lines.append(cut.label)
        for name, value in cut.scores.items():
            lines.append(f"{name}: {value:g}")
        tag = _continuation_tag(cut)
        if tag:
            lines.append(f"continuation{tag}")
        return "\n".join(lines)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._dragging = True
        clicked_cut = self._cut_at(event.position().x())
        if clicked_cut is not None:
            self.cut_selected.emit(clicked_cut.id)
        self._seek_to_x(event.position().x())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self._seek_to_x(event.position().x())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._dragging = False

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        clicked_cut = self._cut_at(event.position().x())
        if clicked_cut is not None:
            self.cut_double_clicked.emit(clicked_cut.id)

    def _seek_to_x(self, x: float) -> None:
        clicked_time = self._time_for_x(x)
        # Update our own visual immediately (optimistic, ignores the
        # _dragging guard in set_position()) so the playhead tracks the
        # mouse smoothly instead of waiting on mpv's round trip.
        self._position = clicked_time
        self.update()
        self.seek_requested.emit(clicked_time)

    def _cut_at(self, x: float) -> Cut | None:
        for cut in self._cuts:
            if self._x_for_time(cut.start) <= x <= self._x_for_time(cut.end):
                return cut
        return None
