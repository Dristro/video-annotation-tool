from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
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

    The MpvPlayer is created lazily on first `load()`, since embedding needs
    a realized native window id (`winId()`), which is only meaningful once
    the widget has actually been shown.
    """

    position_changed = Signal(float)
    duration_changed = Signal(float)
    playback_ended = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player: MpvPlayer | None = None
        self._duration: float = 0.0
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
        self._position_slider.sliderReleased.connect(self._on_seek_end)
        controls.addWidget(self._position_slider, stretch=1)

        self._time_label = QLabel("0:00 / 0:00")
        controls.addWidget(self._time_label)

        layout.addLayout(controls)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(200)
        self._poll_timer.timeout.connect(self._poll_position)

    def _ensure_player(self) -> MpvPlayer:
        if self._player is None:
            self._player = MpvPlayer(self._surface)
        return self._player

    def load(self, path: str) -> None:
        player = self._ensure_player()
        player.load(path)
        self._poll_timer.start()
        self._play_btn.setText("Pause")

    def toggle_pause(self) -> None:
        if self._player is None:
            return
        self._player.toggle_pause()
        self._play_btn.setText("Play" if self._player.is_paused else "Pause")

    def position(self) -> float:
        return self._player.position if self._player else 0.0

    def duration(self) -> float:
        return self._duration

    def seek_to(self, seconds: float) -> None:
        if self._player:
            self._player.seek(seconds, relative=False)

    def seek_relative(self, delta_seconds: float) -> None:
        if self._player:
            self._player.seek(delta_seconds, relative=True)

    def shutdown(self) -> None:
        self._poll_timer.stop()
        if self._player:
            self._player.shutdown()
            self._player = None

    def _on_seek_start(self) -> None:
        self._seeking = True

    def _on_seek_end(self) -> None:
        if self._duration > 0:
            fraction = self._position_slider.value() / 1000.0
            self.seek_to(fraction * self._duration)
        self._seeking = False

    def _poll_position(self) -> None:
        if self._player is None:
            return
        duration = self._player.duration or 0.0
        if duration and abs(duration - self._duration) > 0.01:
            self._duration = duration
            self.duration_changed.emit(duration)

        position = self._player.position
        self.position_changed.emit(position)

        if not self._seeking and self._duration > 0:
            self._position_slider.blockSignals(True)
            self._position_slider.setValue(int((position / self._duration) * 1000))
            self._position_slider.blockSignals(False)

        self._time_label.setText(f"{format_time(position)} / {format_time(self._duration)}")
