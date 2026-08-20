from __future__ import annotations

import locale
from typing import Callable

from vat.playback._mpv_bootstrap import ensure_libmpv_loadable

ensure_libmpv_loadable()

import mpv  # noqa: E402  (must follow the bootstrap workaround above)
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QWidget  # noqa: E402


class VideoSurface(QWidget):
    """A bare QWidget whose native window id is handed to mpv for rendering.

    WA_PaintOnScreen is deliberately NOT set here: Qt's docs call it out as
    unsupported on macOS's Cocoa backend, and setting it produced exactly
    the "QWidget::paintEngine: Should no longer be called" warning spam plus
    a black/non-rendering video surface (Qt's own paint system fighting
    mpv's native NSView-backed rendering). WA_NativeWindow alone is enough
    to force a real native window Qt can hand off via winId().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.setAutoFillBackground(False)


class MpvPlayer:
    """Thin wrapper around python-mpv, bounded to a small on-disk demuxer cache.

    mpv streams from disk rather than loading whole files into memory; we cap
    how far ahead it's allowed to read so playback stays within the project's
    RAM budget even for long videos, per REQUIREMENT.md's non-functional
    requirements (<4GB RAM, chunked loading rather than whole-file loads).
    """

    def __init__(self, surface: VideoSurface):
        # QApplication resets LC_NUMERIC away from "C" during its own init,
        # undoing python-mpv's import-time fix. libmpv hard-aborts the
        # process if LC_NUMERIC isn't "C" when the player is created, so
        # re-assert it right here rather than relying on import order.
        locale.setlocale(locale.LC_NUMERIC, "C")
        self._mpv = mpv.MPV(
            wid=str(int(surface.winId())),
            # Deliberately no `vo=` override: mpv's default ("gpu"/libplacebo)
            # is what actually supports wid-based window embedding on macOS.
            # `vo=libmpv` is a *different* thing -- it's the driver used for
            # the C render API (rendering into an offscreen FBO you manage
            # yourself), not for embedding via a native window id. Setting it
            # here made mpv create its own context without ever drawing into
            # this widget's window: audio/seeking worked, video stayed blank.
            hwdec="auto",
            demuxer_max_bytes="64MiB",
            demuxer_max_back_bytes="16MiB",
            demuxer_readahead_secs=10,
            cache=True,
            keep_open="yes",
            osc=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
            ytdl=False,
        )

    def load(self, path: str) -> None:
        self._mpv.play(path)

    def play(self) -> None:
        self._mpv.pause = False

    def pause(self) -> None:
        self._mpv.pause = True

    def toggle_pause(self) -> None:
        self._mpv.pause = not self._mpv.pause

    @property
    def is_paused(self) -> bool:
        return bool(self._mpv.pause)

    def seek(self, seconds: float, relative: bool = False) -> None:
        mode = "relative" if relative else "absolute"
        self._mpv.seek(seconds, mode)

    @property
    def position(self) -> float:
        return self._mpv.time_pos or 0.0

    @property
    def duration(self) -> float | None:
        return self._mpv.duration

    def observe_position(self, callback: Callable[[float], None]) -> None:
        self._mpv.observe_property("time-pos", lambda name, value: callback(value or 0.0))

    def observe_end_file(self, callback: Callable[[], None]) -> None:
        self._mpv.event_callback("end-file")(lambda event: callback())

    def shutdown(self) -> None:
        self._mpv.terminate()
