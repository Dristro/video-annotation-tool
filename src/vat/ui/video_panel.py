from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from vat.playback.mpv_player import MpvPlayer, VideoSurface


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player: MpvPlayer | None = None
        self._position: float = 0.0
        self._duration: float = 0.0
        self._is_paused: bool = False
        self._seeking = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._surface = VideoSurface(self)
        self._surface.setMinimumHeight(240)
        layout.addWidget(self._surface, stretch=1)

        controls = QHBoxLayout()
        self._play_btn = QPushButton("Play")
        self._play_btn.clicked.connect(self.toggle_pause)
        controls.addWidget(self._play_btn)

        self._position_slider = QSlider(Qt.Orientation.Horizontal)
        self._position_slider.setRange(0, 1000)
        self._position_slider.sliderPressed.connect(self._on_seek_start)
        # sliderMoved fires continuously while dragging (unlike valueChanged,
        # it only fires for user drags, not programmatic setValue calls from
        # _handle_position) -- seeking on every move is what makes scrubbing
        # live instead of only jumping once the mouse is released.
        self._position_slider.sliderMoved.connect(self._on_slider_moved)
        self._position_slider.sliderReleased.connect(self._on_seek_end)
        controls.addWidget(self._position_slider, stretch=1)

        self._time_label = QLabel("0:00 / 0:00")
        controls.addWidget(self._time_label)

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

    def _on_seek_start(self) -> None:
        self._seeking = True

    def _on_slider_moved(self, value: int) -> None:
        if self._duration > 0:
            self.seek_to((value / 1000.0) * self._duration)

    def _on_seek_end(self) -> None:
        # The last sliderMoved already seeked to this value; _seeking just
        # needs clearing so _handle_position resumes driving the slider from
        # mpv's actual position again.
        self._seeking = False

    def _handle_position(self, value: float) -> None:
        self._position = value
        if not self._seeking and self._duration > 0:
            self._position_slider.blockSignals(True)
            self._position_slider.setValue(int((value / self._duration) * 1000))
            self._position_slider.blockSignals(False)
        self._time_label.setText(f"{format_time(value)} / {format_time(self._duration)}")

    def _handle_duration(self, value: float) -> None:
        self._duration = value

    def _handle_pause(self, paused: bool) -> None:
        self._is_paused = paused
        self._play_btn.setText("Play" if paused else "Pause")
