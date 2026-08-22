from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from vat.media.thumbnails import get_or_create_thumbnail, thumbnail_path
from vat.media.video_scanner import VideoInfo


class ThumbnailLoader(QObject):
    """Background loader for playlist thumbnails, one video at a time.

    `refresh_playlist()` used to call `get_or_create_thumbnail()` directly
    for every video, synchronously, on the main thread -- fine once a
    thumbnail is cached (just a file-exists check), but the *first*
    extraction blocks on an `ffmpeg` subprocess, and a video ffmpeg can't
    thumbnail (corrupt file, unsupported edge case, timeout) never gets a
    cache file written, so every single subsequent `refresh_playlist()`
    call -- which fires on nearly every mutating action: add/edit/delete a
    cut, mark annotated, etc., not just on project open -- retried the
    same doomed extraction and re-blocked the main thread each time.
    Reported as a real bug: clicking "Mark Annotated" produced a
    multi-second hang with the spinning-wait cursor. Same
    background-thread-plus-Signal fix as WaveformLoader.
    """

    loaded = Signal(str, str)  # rel_path, thumbnail path ("" if extraction failed)

    def __init__(self):
        super().__init__()

    def load_missing(self, videos: list[VideoInfo], cache_dir: str) -> None:
        """For each video, emit its thumbnail path immediately if already
        cached (a cheap file-exists check -- no need to hop to a thread
        just to report what's already on disk), otherwise kick off
        extraction on a background thread and emit once it's done.
        """
        for video in videos:
            cached = thumbnail_path(video.path, cache_dir)
            if cached.exists():
                self.loaded.emit(video.rel_path, str(cached))
                continue
            threading.Thread(
                target=self._run, args=(video.rel_path, video.path, cache_dir), daemon=True
            ).start()

    def _run(self, rel_path: str, video_path: str, cache_dir: str) -> None:
        result = get_or_create_thumbnail(video_path, cache_dir)
        self.loaded.emit(rel_path, result or "")
