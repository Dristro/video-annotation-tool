from __future__ import annotations

import threading

from vat.media.video_scanner import probe_duration

# Bytes read from the head of the next queued video to warm the OS disk
# cache so mpv's own read-ahead starts hot when the user switches to it.
# The bytes are discarded immediately -- the OS page cache does the actual
# memory-holding, bounded by system memory pressure, rather than us pinning
# a buffer in the app's own RAM. This matches the requirement to fetch only
# a starting chunk ahead of time rather than loading a whole video.
PREFETCH_CHUNK_BYTES = 8 * 1024 * 1024  # 8 MiB


class Preloader:
    """Best-effort background warm-up for the next video in the playlist queue."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def preload(self, path: str) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return  # a preload is already in flight; skip rather than pile up
            self._thread = threading.Thread(target=self._run, args=(path,), daemon=True)
            self._thread.start()

    @staticmethod
    def _run(path: str) -> None:
        try:
            probe_duration(path)
            with open(path, "rb") as f:
                f.read(PREFETCH_CHUNK_BYTES)
        except OSError:
            pass
