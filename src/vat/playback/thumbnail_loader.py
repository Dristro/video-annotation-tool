from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from vat.media.thumbnails import get_or_create_thumbnail, thumbnail_path
from vat.media.video_scanner import VideoInfo

MAX_WORKERS = 3
# Delay before the Nth retry of a failed extraction, in seconds. After the
# last one is used up the video is given up on for the rest of the
# session. Long enough that a refresh_playlist() storm can never re-run a
# doomed extraction on every click (the freeze this loader exists to
# prevent), short enough that a transient failure -- a drive that was
# briefly unmounted, a file still being copied in -- heals itself within a
# normal working session instead of needing an app restart.
RETRY_DELAYS_SECONDS = (30.0, 120.0, 600.0)

# Indirection so tests can drive the retry clock without patching the
# global time.monotonic (which the test harness itself depends on).
_now = time.monotonic


@dataclass
class _State:
    done: bool = False  # cached, extracted, or given up: never look again
    in_flight: bool = False
    failures: int = 0
    next_retry_at: float = 0.0  # monotonic time; only meaningful after a failure


class ThumbnailLoader(QObject):
    """Background loader for playlist thumbnails, through a small worker pool.

    `refresh_playlist()` used to call `get_or_create_thumbnail()` directly
    for every video, synchronously, on the main thread -- fine once a
    thumbnail is cached (just a file-exists check), but the *first*
    extraction blocks on an `ffmpeg` subprocess. That was moved off the
    main thread; the naive version of that fix (one fresh
    `threading.Thread` per uncached video, every call) turned out to have
    exactly the same symptom for a different reason, and is what this
    class's queue + per-video state exist to prevent:

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
    - **Never re-run a failed extraction on the next call.** `_states`
      keys on `(video path, cache dir)`. `refresh_playlist()` fires on
      nearly every mutating action -- add/edit/delete a cut, mark
      annotated, undo, ... -- not just on project open, and a video whose
      extraction *fails* (corrupt file, unsupported edge case, timeout)
      never gets a cache file written, so without this every one of those
      actions re-queued the same doomed extraction forever. That was
      self-perpetuating in the worst way: the extraction storm was itself
      slow enough that the cache never filled up, which guaranteed another
      full storm on the next action. A failure is instead retried only
      after a growing delay (`RETRY_DELAYS_SECONDS`), and given up on for
      the session once those are exhausted -- so a transient failure heals
      without a restart, but a permanent one costs at most a handful of
      attempts per session no matter how many refreshes happen.

    The consequence is that a rebuilt playlist does *not* get its
    thumbnails re-emitted -- `PlaylistPanel` caches the icons it has been
    given and re-applies them across `set_videos()` rebuilds instead.

    `prioritize()` lets the playlist move whatever rows are currently on
    screen to the front of the queue, so scrolling straight to the bottom
    of a long list doesn't mean waiting for everything above it first.
    """

    loaded = Signal(str, str)  # rel_path, thumbnail path ("" if extraction failed)

    def __init__(self, max_workers: int = MAX_WORKERS) -> None:
        super().__init__()
        self._max_workers = max(1, max_workers)
        self._lock = threading.Lock()
        self._queue: deque[tuple[str, str, str]] = deque()  # (rel_path, video_path, cache_dir)
        self._states: dict[tuple[str, str], _State] = {}  # (video_path, cache_dir)
        self._running_workers = 0

    def load_missing(self, videos: list[VideoInfo], cache_dir: str) -> None:
        """For each video not already handled this session, emit its
        thumbnail path immediately if already cached (a cheap file-exists
        check -- ~8 ms for 289 videos, no need to hop to a thread just to
        report what's already on disk), otherwise queue it for extraction
        on the worker pool and emit once it's done. A previously failed
        video is re-queued only once its retry delay has elapsed.
        """
        now = _now()
        fresh = []
        with self._lock:
            for video in videos:
                key = (video.path, cache_dir)
                state = self._states.get(key)
                if state is None:
                    state = self._states[key] = _State()
                elif state.done or state.in_flight or now < state.next_retry_at:
                    continue
                state.in_flight = True
                fresh.append(video)

        cached: list[tuple[str, str]] = []
        queued: list[tuple[str, str, str]] = []
        for video in fresh:
            path = thumbnail_path(video.path, cache_dir)
            if path.exists():
                cached.append((video.rel_path, str(path)))
                with self._lock:
                    self._states[(video.path, cache_dir)] = _State(done=True)
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

    def prioritize(self, rel_paths: list[str]) -> None:
        """Move the queued entries for `rel_paths` (in that order) ahead of
        everything else still waiting. Entries already being extracted are
        unaffected; unknown rel_paths are ignored. Cheap: one stable sort
        of the pending queue under the lock, no thread interaction.
        """
        if not rel_paths:
            return
        rank = {rel: index for index, rel in enumerate(rel_paths)}
        with self._lock:
            if not self._queue:
                return
            ordered = sorted(self._queue, key=lambda item: rank.get(item[0], len(rank)))
            self._queue = deque(ordered)

    def pending_rel_paths(self) -> list[str]:
        """Queue order snapshot, for tests and diagnostics."""
        with self._lock:
            return [item[0] for item in self._queue]

    def _worker(self) -> None:
        while True:
            with self._lock:
                if not self._queue:
                    self._running_workers -= 1
                    return
                rel_path, video_path, cache_dir = self._queue.popleft()
            result = get_or_create_thumbnail(video_path, cache_dir)
            with self._lock:
                state = self._states.setdefault((video_path, cache_dir), _State())
                state.in_flight = False
                if result:
                    state.done = True
                else:
                    state.failures += 1
                    if state.failures > len(RETRY_DELAYS_SECONDS):
                        state.done = True  # give up for this session
                    else:
                        state.next_retry_at = _now() + RETRY_DELAYS_SECONDS[state.failures - 1]
            self.loaded.emit(rel_path, result or "")
