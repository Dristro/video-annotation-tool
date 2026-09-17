"""Direct tests for playback/mpv_player.py against a fake `mpv` module.

Real libmpv playback isn't unit-testable (needs a display, a GL context
and real media), but everything this module does *around* libmpv is:
the locale guard, the render-API configuration (vo=libmpv, no wid), the
bounded cache options, the observer plumbing, the render-context
lifecycle, and the shutdown order. The fake is swapped in at
`mpv_player.mpv` (the module attribute), since the real module is
already imported process-wide by the UI tests.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.playback import mpv_player as mpv_player_module  # noqa: E402
from vat.playback.mpv_player import MpvPlayer, VideoSurface  # noqa: E402


class FakeMPV:
    instances: list["FakeMPV"] = []

    def __init__(self, **options) -> None:
        self.options = options
        self.observers: dict[str, list] = {}
        self.event_callbacks: dict[str, list] = {}
        self.calls: list[tuple] = []
        self.pause = None
        self.speed = None
        FakeMPV.instances.append(self)

    def observe_property(self, name, callback) -> None:
        self.observers.setdefault(name, []).append(callback)

    def event_callback(self, name):
        def _register(fn):
            self.event_callbacks.setdefault(name, []).append(fn)
            return fn
        return _register

    def play(self, path) -> None:
        self.calls.append(("play", path))

    def seek(self, seconds, mode) -> None:
        self.calls.append(("seek", seconds, mode))

    def terminate(self) -> None:
        self.calls.append(("terminate",))


class FakeRenderContext:
    instances: list["FakeRenderContext"] = []

    def __init__(self, core, api, opengl_init_params=None) -> None:
        self.core = core
        self.api = api
        self.opengl_init_params = opengl_init_params
        self.update_cb = None
        self.calls: list[tuple] = []
        FakeRenderContext.instances.append(self)

    def render(self, **kwargs) -> None:
        self.calls.append(("render", kwargs))

    def free(self) -> None:
        self.calls.append(("free",))


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fake_mpv(monkeypatch) -> SimpleNamespace:
    FakeMPV.instances.clear()
    FakeRenderContext.instances.clear()
    fake = SimpleNamespace(
        MPV=FakeMPV,
        MpvRenderContext=FakeRenderContext,
        MpvGlGetProcAddressFn=lambda fn: ("wrapped", fn),
    )
    monkeypatch.setattr(mpv_player_module, "mpv", fake)
    return fake


class TestMpvPlayer:
    def test_lc_numeric_is_forced_to_c_before_the_core_is_created(self, fake_mpv, monkeypatch) -> None:
        # libmpv hard-aborts the process (not a Python exception) if
        # LC_NUMERIC isn't "C" at MPV() time, and QApplication resets it
        # during its own init -- so the guard must run right before
        # construction, not at import time.
        order = []
        monkeypatch.setattr(
            mpv_player_module.locale, "setlocale",
            lambda category, value=None: order.append(("setlocale", category, value)),
        )
        original_init = FakeMPV.__init__

        def _init(self, **options):
            order.append(("MPV",))
            original_init(self, **options)

        monkeypatch.setattr(FakeMPV, "__init__", _init)

        MpvPlayer()

        assert order[0] == ("setlocale", mpv_player_module.locale.LC_NUMERIC, "C")
        assert order[1] == ("MPV",)

    def test_core_uses_render_api_driver_without_a_window_id(self, fake_mpv) -> None:
        player = MpvPlayer()
        options = player.core.options
        assert options["vo"] == "libmpv"
        assert "wid" not in options

    def test_demuxer_cache_is_bounded(self, fake_mpv) -> None:
        options = MpvPlayer().core.options
        assert options["demuxer_max_bytes"] == "64MiB"
        assert options["demuxer_max_back_bytes"] == "16MiB"
        assert options["cache"] is True
        assert options["ytdl"] is False and options["osc"] is False

    def test_transport_calls_delegate_to_the_core(self, fake_mpv) -> None:
        player = MpvPlayer()
        player.load("/v/a.mp4")
        player.pause()
        player.play()
        player.set_paused(True)
        player.seek(12.0)
        player.seek(-5.0, relative=True)
        player.set_speed(1.5)
        player.shutdown()
        core = player.core
        assert core.calls == [
            ("play", "/v/a.mp4"), ("seek", 12.0, "absolute"), ("seek", -5.0, "relative"), ("terminate",),
        ]
        assert core.pause is True
        assert core.speed == 1.5

    def test_observers_normalise_none_and_types(self, fake_mpv) -> None:
        player = MpvPlayer()
        positions, durations, pauses, ended = [], [], [], []
        player.observe_position(positions.append)
        player.observe_duration(durations.append)
        player.observe_pause(pauses.append)
        player.observe_end_file(lambda: ended.append(True))
        core = player.core

        core.observers["time-pos"][0]("time-pos", None)   # mpv reports None before/after a file
        core.observers["time-pos"][0]("time-pos", 12.5)
        core.observers["duration"][0]("duration", None)
        core.observers["duration"][0]("duration", 300.0)
        core.observers["pause"][0]("pause", None)
        core.observers["pause"][0]("pause", 1)
        core.event_callbacks["end-file"][0](object())

        assert positions == [0.0, 12.5]
        assert durations == [0.0, 300.0]
        assert pauses == [False, True]
        assert ended == [True]

    def test_no_synchronous_property_getters_are_exposed(self, fake_mpv) -> None:
        # The deadlock documented in CLAUDE.md: a synchronous mpv_get_property
        # from the Qt main thread on a timer hangs the app on macOS. The
        # wrapper deliberately has no position/duration/pause getters.
        for name in ("position", "duration", "is_paused", "paused"):
            assert not hasattr(MpvPlayer, name)


class TestVideoSurface:
    def test_get_proc_address_callback_is_cfunctype_wrapped_and_kept_alive(self, qapp, fake_mpv) -> None:
        surface = VideoSurface()
        assert surface._get_proc_address_cfunc == ("wrapped", mpv_player_module._get_proc_address)

    def test_bind_defers_render_context_until_gl_is_initialised(self, qapp, fake_mpv) -> None:
        # No GL context exists until the widget is shown (never, offscreen),
        # and mpv_render_context_create needs a *current* one -- so bind
        # must not create it eagerly.
        surface = VideoSurface()
        surface.bind_player(MpvPlayer().core)
        assert surface._render_ctx is None
        assert FakeRenderContext.instances == []

    def test_initialize_gl_creates_the_context_and_hooks_frame_updates(self, qapp, fake_mpv) -> None:
        surface = VideoSurface()
        core = MpvPlayer().core
        surface.bind_player(core)

        surface.initializeGL()

        ctx = surface._render_ctx
        assert ctx is not None and ctx.core is core and ctx.api == "opengl"
        assert ctx.opengl_init_params == {"get_proc_address": surface._get_proc_address_cfunc}
        # Fires on mpv's thread: must be nothing but the signal's emit.
        assert ctx.update_cb == surface.frame_ready.emit

        surface.initializeGL()  # idempotent: never a second context for the same widget
        assert len(FakeRenderContext.instances) == 1

    def test_paint_is_a_noop_without_a_context_and_renders_with_one(self, qapp, fake_mpv) -> None:
        surface = VideoSurface()
        surface.paintGL()  # nothing bound yet: must not raise
        surface.bind_player(MpvPlayer().core)
        surface.initializeGL()

        surface.paintGL()

        (name, kwargs), = surface._render_ctx.calls
        assert name == "render" and kwargs["flip_y"] is True
        assert set(kwargs["opengl_fbo"]) == {"w", "h", "fbo"}
        assert kwargs["opengl_fbo"]["w"] >= 1 and kwargs["opengl_fbo"]["h"] >= 1

    def test_release_frees_the_context_before_dropping_the_core(self, qapp, fake_mpv) -> None:
        surface = VideoSurface()
        surface.bind_player(MpvPlayer().core)
        surface.initializeGL()
        ctx = surface._render_ctx

        surface.release_player()

        assert ctx.calls == [("free",)]
        assert surface._render_ctx is None and surface._mpv_core is None
        surface.release_player()  # idempotent
        assert ctx.calls == [("free",)]


class TestVideoPanelLifecycle:
    def test_first_load_builds_player_wires_observers_and_applies_speed(self, qapp, fake_mpv) -> None:
        from vat.ui.video_panel import SPEED_STEPS, VideoPanel

        panel = VideoPanel()
        panel._speed_slider.setValue(SPEED_STEPS.index(0.5))

        panel.load("/v/a.mp4")
        panel.load("/v/b.mp4")

        assert len(FakeMPV.instances) == 1  # one core for the whole session
        core = FakeMPV.instances[0]
        assert [c for c in core.calls if c[0] == "play"] == [("play", "/v/a.mp4"), ("play", "/v/b.mp4")]
        assert set(core.observers) >= {"time-pos", "duration", "pause"}
        assert core.speed == 0.5  # slider state re-applied to the fresh core

        # Observer delivery updates the cached values the UI reads.
        core.observers["time-pos"][0]("time-pos", 42.0)
        core.observers["duration"][0]("duration", 120.0)
        qapp.processEvents()
        assert panel.position() == 42.0
        assert panel.duration() == 120.0

    def test_shutdown_frees_render_context_before_terminating_the_core(self, qapp, fake_mpv) -> None:
        from vat.ui.video_panel import VideoPanel

        panel = VideoPanel()
        panel.load("/v/a.mp4")
        panel._surface.initializeGL()
        core = FakeMPV.instances[0]
        ctx = FakeRenderContext.instances[0]
        order = []
        ctx.free = lambda: order.append("free")
        core.terminate = lambda: order.append("terminate")

        panel.shutdown()

        assert order == ["free", "terminate"]
        panel.shutdown()  # idempotent
        assert order == ["free", "terminate"]
