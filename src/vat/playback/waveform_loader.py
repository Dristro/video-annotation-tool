from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from vat.media.waveform import get_or_create_waveform


class WaveformLoader(QObject):
    """Background loader for a video's waveform peaks.

    Unlike Preloader (fire-and-forget, no result to report), this needs to
    hand a result back to the UI thread, hence QObject+Signal -- same
    thread-safety pattern used throughout the codebase for mpv's async
    observers (see CLAUDE.md): the background thread does nothing but
    `emit()`, which Qt auto-queues onto the receiver's thread since the
    emit comes from a different thread than the connected slot lives on.
    Decoding a whole audio track can take noticeably longer than a single
    thumbnail frame grab, so this must never run on the main thread.
    """

    loaded = Signal(str, list)  # video_path, peaks (empty list if extraction failed/no audio)

    def __init__(self):
        super().__init__()

    def load(self, video_path: str, cache_dir: str) -> None:
        # No in-flight dedup like Preloader's -- a video switch fires one
        # load per video, and MainWindow's slot checks the emitted path
        # still matches the *current* video before applying it, so a late
        # result for a video the user already navigated away from is just
        # ignored rather than needing to be cancelled here.
        threading.Thread(target=self._run, args=(video_path, cache_dir), daemon=True).start()

    def _run(self, video_path: str, cache_dir: str) -> None:
        peaks = get_or_create_waveform(video_path, cache_dir) or []
        self.loaded.emit(video_path, peaks)
