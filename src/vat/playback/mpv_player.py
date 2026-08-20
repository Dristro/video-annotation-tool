from __future__ import annotations

import locale
from typing import Callable

from vat.playback._mpv_bootstrap import ensure_libmpv_loadable

ensure_libmpv_loadable()

import mpv  # noqa: E402  (must follow the bootstrap workaround above)
from PySide6.QtCore import Signal  # noqa: E402
from PySide6.QtGui import QOpenGLContext  # noqa: E402
from PySide6.QtOpenGLWidgets import QOpenGLWidget  # noqa: E402


def _get_proc_address(_ctx, name: bytes) -> int:
    context = QOpenGLContext.currentContext()
    if context is None:
        return 0
    address = context.getProcAddress(name)
    return int(address) if address else 0


class VideoSurface(QOpenGLWidget):
    """The widget mpv actually draws into, via its client Render API rather
    than window (`wid`) embedding.

    `wid`-based embedding -- handing mpv a native window id and letting it
    manage that window/view directly -- proved unreliable on macOS across
    two separate real-world attempts: the video kept opening in its own
    separate OS window regardless of `vo` choice or of timing relative to
    the parent window being shown, and closing the app hung indefinitely
    (very likely mpv's Cocoa video output getting stuck in a partial/orphaned
    embedding state). mpv's macOS video output has only limited support for
    embedding into a foreign NSView; the Render API -- where mpv renders
    into an OpenGL framebuffer *we* own, inside a widget *we* fully control,
    with no window handoff at all -- is the approach macOS-targeting mpv
    embeddings (e.g. IINA) actually rely on, and sidesteps the whole class
    of Cocoa window-ownership problems above.

    The render context is created in initializeGL() (called by Qt only once
    a real, current OpenGL context exists for this widget) rather than
    eagerly in __init__, since mpv_render_context_create requires a current
    GL context on the calling thread.
    """

    frame_ready = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mpv_core: mpv.MPV | None = None
        self._render_ctx: mpv.MpvRenderContext | None = None
        # ctypes CFUNCTYPE-wrapped callback, kept alive for as long as the
        # render context might call it -- ctypes callback trampolines get
        # garbage-collected like anything else if nothing references them,
        # which would crash mpv the next time it tried to call a freed
        # function pointer. Assigning a plain Python function directly (no
        # explicit CFUNCTYPE wrap) also doesn't work here: unlike passing a
        # callable as a ctypes *function call* argument, assigning to a
        # ctypes Structure field typed as a CFUNCTYPE requires an actual
        # instance of that CFUNCTYPE, not a bare function -- reproduced this
        # for real (TypeError: expected CFunctionType instance, got
        # function) before adding the explicit wrap below.
        self._get_proc_address_cfunc = mpv.MpvGlGetProcAddressFn(_get_proc_address)
        self.frame_ready.connect(self.update)

    def bind_player(self, mpv_core: mpv.MPV) -> None:
        self._mpv_core = mpv_core
        if self.isValid():
            # A GL context already exists (widget already shown once) --
            # initializeGL() won't fire again on its own, so set up the
            # render context here instead.
            self.makeCurrent()
            self._create_render_context()
            self.doneCurrent()
        else:
            self.update()  # triggers initializeGL() once the widget is shown

    def release_player(self) -> None:
        if self._render_ctx is not None:
            self.makeCurrent()
            self._render_ctx.free()
            self.doneCurrent()
            self._render_ctx = None
        self._mpv_core = None

    def initializeGL(self) -> None:
        self._create_render_context()

    def _create_render_context(self) -> None:
        if self._mpv_core is None or self._render_ctx is not None:
            return
        self._render_ctx = mpv.MpvRenderContext(
            self._mpv_core,
            "opengl",
            opengl_init_params={"get_proc_address": self._get_proc_address_cfunc},
        )
        # Fires on mpv's own thread whenever a new frame is ready; must do
        # nothing but emit() (thread-safe from any thread). The connected
        # `update` slot runs on this widget's own (main) thread since Qt
        # auto-queues cross-thread signal deliveries.
        self._render_ctx.update_cb = self.frame_ready.emit

    def paintGL(self) -> None:
        if self._render_ctx is None:
            return
        dpr = self.devicePixelRatioF()
        self._render_ctx.render(
            flip_y=True,
            opengl_fbo={
                "w": max(1, int(self.width() * dpr)),
                "h": max(1, int(self.height() * dpr)),
                "fbo": self.defaultFramebufferObject(),
            },
        )


class MpvPlayer:
    """Thin wrapper around python-mpv's core client instance, bounded to a
    small on-disk demuxer cache.

    mpv streams from disk rather than loading whole files into memory; we cap
    how far ahead it's allowed to read so playback stays within the project's
    RAM budget even for long videos, per REQUIREMENT.md's non-functional
    requirements (<4GB RAM, chunked loading rather than whole-file loads).

    Deliberately holds no reference to any widget: rendering is VideoSurface's
    job via the Render API (see its docstring). Callers must pass this
    instance's `core` to `VideoSurface.bind_player()` to actually see video.
    """

    def __init__(self):
        # QApplication resets LC_NUMERIC away from "C" during its own init,
        # undoing python-mpv's import-time fix. libmpv hard-aborts the
        # process if LC_NUMERIC isn't "C" when the player is created, so
        # re-assert it right here rather than relying on import order.
        locale.setlocale(locale.LC_NUMERIC, "C")
        self._mpv = mpv.MPV(
            vo="libmpv",  # required for the Render API: mpv must not manage its own window/view.
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

    @property
    def core(self) -> mpv.MPV:
        return self._mpv

    def load(self, path: str) -> None:
        self._mpv.play(path)

    def play(self) -> None:
        self._mpv.pause = False

    def pause(self) -> None:
        self._mpv.pause = True

    def set_paused(self, paused: bool) -> None:
        self._mpv.pause = paused

    def seek(self, seconds: float, relative: bool = False) -> None:
        mode = "relative" if relative else "absolute"
        self._mpv.seek(seconds, mode)

    # -- Async observers ---------------------------------------------------
    # Deliberately no synchronous position/duration/pause *getters* here.
    # python-mpv's observe_property callbacks fire on its own background
    # event thread via mpv_wait_event, which is safe to call from any
    # thread. A synchronous mpv_get_property call from the Qt main thread,
    # by contrast, blocks on mpv's internal core dispatch lock -- and on
    # macOS, mpv's video output does a dispatch_sync onto the *main queue*
    # during its Cocoa/Metal setup shortly after load(). If the main thread
    # is itself blocked inside mpv_get_property at that moment (e.g. a
    # polling QTimer firing every 200ms), neither side can make progress:
    # the main thread can't return to pump Cocoa's run loop (which mpv's
    # main-queue dispatch needs), and mpv's core thread can't release the
    # lock the main thread is waiting on until that dispatch completes.
    # Reproduced this exact deadlock (via `sample <pid>` thread dumps) when
    # VideoPanel polled `.position`/`.duration` properties on a QTimer --
    # it hung forever, every time, because the timer fired within
    # milliseconds of load(). Callers must use the observers below and
    # cache the values themselves instead.
    def observe_position(self, callback: Callable[[float], None]) -> None:
        self._mpv.observe_property("time-pos", lambda name, value: callback(value or 0.0))

    def observe_duration(self, callback: Callable[[float], None]) -> None:
        self._mpv.observe_property("duration", lambda name, value: callback(value or 0.0))

    def observe_pause(self, callback: Callable[[bool], None]) -> None:
        self._mpv.observe_property("pause", lambda name, value: callback(bool(value)))

    def observe_end_file(self, callback: Callable[[], None]) -> None:
        self._mpv.event_callback("end-file")(lambda event: callback())

    def shutdown(self) -> None:
        self._mpv.terminate()
