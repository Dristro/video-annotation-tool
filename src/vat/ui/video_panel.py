from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from vat.playback.mpv_player import MpvPlayer, VideoSurface

# Discrete playback speed steps for the notched speed slider -- a QSlider
# over these indices rather than a continuous range, so it only ever lands
# on one of these values (no arbitrary in-between speeds).
SPEED_STEPS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
DEFAULT_SPEED_INDEX = SPEED_STEPS.index(1.0)


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


class VideoPanel(QWidget):
    """Center panel: the mpv render surface plus transport controls.

    The MpvPlayer (mpv's core client instance) is created lazily on first
    `load()`. VideoSurface renders it via mpv's Render API rather than
    window embedding -- see VideoSurface's docstring for why.

    Scrubbing lives entirely on TimelineWidget now -- there is no position
    slider here. The two controls used to duplicate the same job (drag to
    seek) with two different circular-handle widgets stacked on top of each
    other; TimelineWidget is the one that also shows cuts, so it's the one
    that stayed.

    Position/duration/pause state is driven entirely by MpvPlayer's async
    property observers, not by polling -- see the long comment in
    MpvPlayer for why a polling QTimer calling into mpv from the Qt main
    thread deadlocks on macOS. The observer callbacks fire on mpv's own
    event thread; they only ever call `.emit()` on the signals below
    (thread-safe), and the actual widget updates happen in the connected
    slots, which Qt automatically runs on this widget's own (main) thread
    since the emit originates from a different thread.
    """

    position_changed = Signal(float)
    duration_changed = Signal(float)
    pause_changed = Signal(bool)
    playback_ended = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._player: MpvPlayer | None = None
        self._position: float = 0.0
        self._duration: float = 0.0
        self._is_paused: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._surface = VideoSurface(self)
        self._surface.setMinimumHeight(240)
        layout.addWidget(self._surface, stretch=1)

        controls = QHBoxLayout()

        self._play_btn = QPushButton("Play")
        self._play_btn.clicked.connect(self.toggle_pause)
        # "Play" and "Pause" are different widths -- without a fixed width
        # the button visibly resizes (and everything else in the row
        # shifts) every time playback toggles. Size it once, to fit
        # whichever label is wider, padded for the button's own chrome.
        metrics = self._play_btn.fontMetrics()
        button_width = max(metrics.horizontalAdvance("Play"), metrics.horizontalAdvance("Pause")) + 24
        self._play_btn.setFixedWidth(button_width)
        controls.addWidget(self._play_btn)

        self._time_label = QLabel("0:00 / 0:00")
        controls.addWidget(self._time_label, stretch=1)

        # Playback speed: a notched (discrete-step) slider rather than a
        # continuous one, so it only ever lands on one of SPEED_STEPS.
        self._speed_label = QLabel("1.0x")
        controls.addWidget(self._speed_label)
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(0, len(SPEED_STEPS) - 1)
        self._speed_slider.setValue(DEFAULT_SPEED_INDEX)
        self._speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._speed_slider.setTickInterval(1)
        self._speed_slider.setSingleStep(1)
        self._speed_slider.setPageStep(1)
        self._speed_slider.setFixedWidth(120)
        self._speed_slider.setToolTip("Playback speed")
        self._speed_slider.valueChanged.connect(self._on_speed_index_changed)
        controls.addWidget(self._speed_slider)

        layout.addLayout(controls)

        self.position_changed.connect(self._handle_position)
        self.duration_changed.connect(self._handle_duration)
        self.pause_changed.connect(self._handle_pause)

    def _ensure_player(self) -> MpvPlayer:
        if self._player is None:
            self._player = MpvPlayer()
            self._surface.bind_player(self._player.core)
            # These callbacks run on mpv's background event thread -- they
            # must do nothing but emit(), never touch widgets directly.
            self._player.observe_position(self.position_changed.emit)
            self._player.observe_duration(self.duration_changed.emit)
            self._player.observe_pause(self.pause_changed.emit)
            # The slider may already be off 1x (e.g. left that way from a
            # previous video) -- apply it to this freshly-created player
            # instead of silently reverting to mpv's own default speed.
            self._player.set_speed(SPEED_STEPS[self._speed_slider.value()])
        return self._player

    def load(self, path: str) -> None:
        player = self._ensure_player()
        player.load(path)

    def toggle_pause(self) -> None:
        if self._player is None:
            return
        self._player.set_paused(not self._is_paused)

    def position(self) -> float:
        return self._position

    def duration(self) -> float:
        return self._duration

    def seek_to(self, seconds: float) -> None:
        if self._player:
            self._player.seek(seconds, relative=False)

    def seek_relative(self, delta_seconds: float) -> None:
        if self._player:
            self._player.seek(delta_seconds, relative=True)

    def shutdown(self) -> None:
        # Release the render context (needs the core mpv handle still alive)
        # before terminating the core itself.
        self._surface.release_player()
        if self._player:
            self._player.shutdown()
            self._player = None

    def _on_speed_index_changed(self, index: int) -> None:
        speed = SPEED_STEPS[index]
        self._speed_label.setText(f"{speed:g}x")
        if self._player:
            self._player.set_speed(speed)

    def _handle_position(self, value: float) -> None:
        self._position = value
        self._time_label.setText(f"{format_time(value)} / {format_time(self._duration)}")

    def _handle_duration(self, value: float) -> None:
        self._duration = value

    def _handle_pause(self, paused: bool) -> None:
        self._is_paused = paused
        self._play_btn.setText("Play" if paused else "Pause")
