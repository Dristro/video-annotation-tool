from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from vat.media.waveform import get_or_create_waveform


class WaveformLoader(QObject):
    """Background loader for a video's waveform peaks: one worker thread,
    latest request wins.

    Unlike Preloader (fire-and-forget, no result to report), this needs to
    hand a result back to the UI thread, hence QObject+Signal -- same
    thread-safety pattern used throughout the codebase for mpv's async
    observers (see CLAUDE.md): the background thread does nothing but
    `emit()`, which Qt auto-queues onto the receiver's thread since the
    emit comes from a different thread than the connected slot lives on.
    Decoding a whole audio track can take noticeably longer than a single
    thumbnail frame grab, so this must never run on the main thread.

    It also must not pile up: a full audio decode per video is far more
    expensive than a thumbnail grab, and stepping quickly through the
    playlist (Up/Down held) fires one `load()` per video passed over. The
    first version started one thread per call and only discarded the
    *results* (MainWindow ignores a result whose path no longer matches
    the current video), so every skipped-over video still got fully
    decoded. Now there is exactly one worker and a single "next request"
    slot: a new `load()` overwrites whatever was waiting, so at most the
    in-flight decode plus the most recent request ever run. The path check
    on the receiving side stays as the second line of defence for the
    in-flight one.
    """

    loaded = Signal(str, list)  # video_path, peaks (empty list if extraction failed/no audio)

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._pending: tuple[str, str] | None = None
        self._worker_running = False

    def load(self, video_path: str, cache_dir: str) -> None:
        with self._lock:
            self._pending = (video_path, cache_dir)
            if self._worker_running:
                return  # the worker picks up the newest request when it's done
            self._worker_running = True
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        while True:
            with self._lock:
                if self._pending is None:
                    self._worker_running = False
                    return
                video_path, cache_dir = self._pending
                self._pending = None
            peaks = get_or_create_waveform(video_path, cache_dir) or []
            self.loaded.emit(video_path, peaks)
