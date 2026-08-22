from __future__ import annotations

import threading
from collections import deque

from PySide6.QtCore import QObject, Signal

from vat.media.thumbnails import get_or_create_thumbnail, thumbnail_path
from vat.media.video_scanner import VideoInfo

MAX_WORKERS = 3


class ThumbnailLoader(QObject):
    """Background loader for playlist thumbnails, through a small worker pool.

    `refresh_playlist()` used to call `get_or_create_thumbnail()` directly
    for every video, synchronously, on the main thread -- fine once a
    thumbnail is cached (just a file-exists check), but the *first*
    extraction blocks on an `ffmpeg` subprocess. That was moved off the
    main thread; the naive version of that fix (one fresh
    `threading.Thread` per uncached video, every call) turned out to have
    exactly the same symptom for a different reason, and is what this
    class's queue + `_seen` set exist to prevent:

    - **One thread per video is not free on the calling thread.**
      `Thread.start()` blocks until the new thread is actually running,
      and each of those threads immediately forks an `ffmpeg` subprocess.
      Measured against the real 289-video project this tool was written
      for: `load_missing()` blocked the *main* thread for ~1.5 s per call
      (289 thread spawns + 289 concurrent `ffmpeg` processes saturating
      the machine at ~800% CPU). Reported, again, as clicking "Mark
      Annotated" freezing the app with the spinning-wait cursor. Fixed by
      queueing the work and draining it with at most `MAX_WORKERS`
      threads, so the calling thread only ever does a few dict lookups
      plus (at most) `MAX_WORKERS` thread spawns.
    - **Never look at the same video twice in a session.** `_seen` keys on
      `(video path, cache dir)`. `refresh_playlist()` fires on nearly every
      mutating action -- add/edit/delete a cut, mark annotated, undo, ... --
      not just on project open, and a video whose extraction *fails*
      (corrupt file, unsupported edge case, timeout) never gets a cache
      file written, so without this every one of those actions re-queued
      the same doomed extraction forever. That was self-perpetuating in
      the worst way: the extraction storm was itself slow enough that the
      cache never filled up, which guaranteed another full storm on the
      next action.

    The consequence of `_seen` is that a rebuilt playlist does *not* get
    its thumbnails re-emitted -- `PlaylistPanel` caches the icons it has
    been given and re-applies them across `set_videos()` rebuilds instead.
    """

    loaded = Signal(str, str)  # rel_path, thumbnail path ("" if extraction failed)

    def __init__(self, max_workers: int = MAX_WORKERS):
        super().__init__()
        self._max_workers = max(1, max_workers)
        self._lock = threading.Lock()
        self._queue: deque[tuple[str, str, str]] = deque()  # (rel_path, video_path, cache_dir)
        self._seen: set[tuple[str, str]] = set()  # (video_path, cache_dir)
        self._running_workers = 0

    def load_missing(self, videos: list[VideoInfo], cache_dir: str) -> None:
        """For each video not already handled this session, emit its
        thumbnail path immediately if already cached (a cheap file-exists
        check -- ~8 ms for 289 videos, no need to hop to a thread just to
        report what's already on disk), otherwise queue it for extraction
        on the worker pool and emit once it's done.
        """
        fresh = []
        with self._lock:
            for video in videos:
                key = (video.path, cache_dir)
                if key in self._seen:
                    continue
                self._seen.add(key)
                fresh.append(video)

        cached: list[tuple[str, str]] = []
        queued: list[tuple[str, str, str]] = []
        for video in fresh:
            path = thumbnail_path(video.path, cache_dir)
            if path.exists():
                cached.append((video.rel_path, str(path)))
            else:
                queued.append((video.rel_path, video.path, cache_dir))

        for rel_path, path in cached:
            self.loaded.emit(rel_path, path)

        if not queued:
            return
        with self._lock:
            self._queue.extend(queued)
            to_start = min(self._max_workers - self._running_workers, len(self._queue))
            self._running_workers += to_start
        for _ in range(to_start):
            threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        while True:
            with self._lock:
                if not self._queue:
                    self._running_workers -= 1
                    return
                rel_path, video_path, cache_dir = self._queue.popleft()
            result = get_or_create_thumbnail(video_path, cache_dir)
            self.loaded.emit(rel_path, result or "")
