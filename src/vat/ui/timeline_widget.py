from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from vat.models.cut import Cut
from vat.ui.video_panel import format_time
from vat.utils.colors import color_for_label, contrasting_text_color

TRACK_HEIGHT = 28
TRACK_MARGIN_TOP = 12
EDGE_GRAB_PX = 6  # how close a press has to be to a cut's start/end to grab it for resizing
MIN_CUT_LENGTH_SECONDS = 0.1  # keeps a drag from collapsing a cut to zero/negative length live
WAVEFORM_HEIGHT = 24
WAVEFORM_MARGIN_TOP = TRACK_MARGIN_TOP + TRACK_HEIGHT + 6


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
    start. Pressing within EDGE_GRAB_PX of a cut's left or right edge
    drags that edge instead of scrubbing -- resizing it live -- and emits
    cut_resized on release with the final range; MainWindow (not this
    widget, which owns no Project reference) decides whether to commit it,
    including the same overlap-confirmation prompt as Add/Edit Annotation.
    """

    seek_requested = Signal(float)  # seconds
    cut_selected = Signal(str)  # cut id
    cut_double_clicked = Signal(str)  # cut id
    cut_resized = Signal(str, float, float)  # cut id, new start, new end

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(WAVEFORM_MARGIN_TOP + WAVEFORM_HEIGHT + 12)
        self._duration: float = 0.0
        self._position: float = 0.0
        self._cuts: list[Cut] = []
        # Peak amplitudes (0.0-1.0) evenly spanning the whole video,
        # regardless of its length -- None means "no waveform to show yet"
        # (still loading, extraction failed, or no video loaded), not "flat
        # audio". Provided by MainWindow via WaveformLoader; this widget
        # never touches ffmpeg/the filesystem itself.
        self._waveform: list[float] | None = None
        # While the user is dragging, the position shown must track the
        # drag itself, not whatever mpv's async position observer reports
        # in the meantime (which lags slightly behind a seek and would
        # otherwise make the playhead jitter/fight the mouse).
        self._dragging = False
        # Edge-resize drag state -- mutually exclusive with self._dragging
        # (a press either grabs an edge or starts a scrub, never both).
        # _live_resize holds the in-progress (start, end) shown while
        # dragging, kept separate from the real Cut until release so nothing
        # is committed mid-drag.
        self._resize_cut_id: str | None = None
        self._resize_edge: str | None = None  # "start" | "end"
        self._live_resize: tuple[float, float] | None = None

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

    def set_waveform(self, peaks: list[float] | None) -> None:
        self._waveform = peaks
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
            if cut.id == self._resize_cut_id and self._live_resize is not None:
                start, end = self._live_resize
            else:
                start, end = cut.start, cut.end
            start_x = self._x_for_time(start)
            end_x = self._x_for_time(end)
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

        self._paint_waveform(painter)

        if self._duration > 0:
            playhead_x = self._x_for_time(self._position)
            painter.setPen(QPen(Qt.GlobalColor.red, 2))
            painter.drawLine(int(playhead_x), 0, int(playhead_x), self.height())

    def _paint_waveform(self, painter: QPainter) -> None:
        waveform_rect = QRectF(2, WAVEFORM_MARGIN_TOP, max(1, self.width() - 4), WAVEFORM_HEIGHT)
        painter.setPen(QPen(Qt.GlobalColor.darkGray))
        painter.setBrush(Qt.GlobalColor.lightGray if self._waveform else QColor(0, 0, 0, 0))
        painter.drawRoundedRect(waveform_rect, 3, 3)
        if not self._waveform:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(70, 90, 130))
        center_y = WAVEFORM_MARGIN_TOP + WAVEFORM_HEIGHT / 2
        bar_width = max(1.0, waveform_rect.width() / len(self._waveform))
        for i, peak in enumerate(self._waveform):
            bar_height = max(1.0, peak * (WAVEFORM_HEIGHT / 2))
            x = waveform_rect.left() + i * bar_width
            painter.drawRect(QRectF(x, center_y - bar_height, bar_width, bar_height * 2))

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
        if cut.justification:
            lines.append(cut.justification)
        tag = _continuation_tag(cut)
        if tag:
            lines.append(f"continuation{tag}")
        return "\n".join(lines)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        x = event.position().x()
        edge = self._edge_at(x)
        if edge is not None:
            cut, which = edge
            self._resize_cut_id = cut.id
            self._resize_edge = which
            self._live_resize = (cut.start, cut.end)
            self.cut_selected.emit(cut.id)
            self.update()
            return
        self._dragging = True
        clicked_cut = self._cut_at(x)
        if clicked_cut is not None:
            self.cut_selected.emit(clicked_cut.id)
        self._seek_to_x(x)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._resize_cut_id is not None:
            self._update_live_resize(event.position().x())
        elif self._dragging:
            self._seek_to_x(event.position().x())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._resize_cut_id is not None:
            cut_id = self._resize_cut_id
            start, end = self._live_resize
            self._resize_cut_id = None
            self._resize_edge = None
            self._live_resize = None
            self.update()
            self.cut_resized.emit(cut_id, start, end)
            return
        self._dragging = False

    def _edge_at(self, x: float) -> tuple[Cut, str] | None:
        """(cut, "start"|"end") if x is within EDGE_GRAB_PX of that cut's
        edge, else None. Checked before treating a press as a scrub.
        """
        for cut in self._cuts:
            if abs(x - self._x_for_time(cut.start)) <= EDGE_GRAB_PX:
                return cut, "start"
            if abs(x - self._x_for_time(cut.end)) <= EDGE_GRAB_PX:
                return cut, "end"
        return None

    def _update_live_resize(self, x: float) -> None:
        if self._live_resize is None:
            return
        start, end = self._live_resize
        new_time = self._time_for_x(x)
        if self._resize_edge == "start":
            new_time = max(0.0, min(new_time, end - MIN_CUT_LENGTH_SECONDS))
            self._live_resize = (new_time, end)
        else:
            upper_bound = self._duration if self._duration > 0 else new_time
            new_time = min(upper_bound, max(new_time, start + MIN_CUT_LENGTH_SECONDS))
            self._live_resize = (start, new_time)
        self.update()

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
