from typing import Callable
from PySide6.QtCore import QCoreApplication
import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from vat.media.video_scanner import VideoInfo  # noqa: E402
from vat.playback import thumbnail_loader as thumbnail_loader_module  # noqa: E402
from vat.playback.thumbnail_loader import ThumbnailLoader  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def _run_event_loop_until(qapp, predicate: Callable[[], bool], timeout_ms=5000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
    return False


def test_already_cached_thumbnail_emitted_immediately_without_extraction(qapp, tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    from vat.media.thumbnails import thumbnail_path

    video = VideoInfo(path=str(tmp_path / "a.mp4"), rel_path="a.mp4")
    cached_file = thumbnail_path(video.path, str(cache_dir))
    cached_file.write_bytes(b"fake jpeg")

    extraction_calls = []
    monkeypatch.setattr(
        thumbnail_loader_module, "get_or_create_thumbnail",
        lambda *a, **k: extraction_calls.append(a) or "should not be called",
    )

    loader = ThumbnailLoader()
    results = []
    loader.loaded.connect(lambda rel, path: results.append((rel, path)))

    loader.load_missing([video], str(cache_dir))

    # Cached path is emitted synchronously (no thread hop needed), so it
    # must already be there without even pumping the event loop.
    assert results == [("a.mp4", str(cached_file))]
    assert extraction_calls == []


def test_missing_thumbnail_extracted_in_background_and_emitted(qapp, tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache"
    video = VideoInfo(path=str(tmp_path / "b.mp4"), rel_path="b.mp4")

    monkeypatch.setattr(
        thumbnail_loader_module, "get_or_create_thumbnail", lambda path, cache_dir: "/fake/thumb.jpg"
    )

    loader = ThumbnailLoader()
    results = []
    loader.loaded.connect(lambda rel, path: results.append((rel, path)))

    loader.load_missing([video], str(cache_dir))

    assert _run_event_loop_until(qapp, lambda: len(results) == 1)
    assert results[0] == ("b.mp4", "/fake/thumb.jpg")


def test_extraction_failure_emits_empty_string(qapp, tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache"
    video = VideoInfo(path=str(tmp_path / "c.mp4"), rel_path="c.mp4")

    monkeypatch.setattr(thumbnail_loader_module, "get_or_create_thumbnail", lambda path, cache_dir: None)

    loader = ThumbnailLoader()
    results = []
    loader.loaded.connect(lambda rel, path: results.append((rel, path)))

    loader.load_missing([video], str(cache_dir))

    assert _run_event_loop_until(qapp, lambda: len(results) == 1)
    assert results[0] == ("c.mp4", "")


def test_failed_extraction_is_not_retried_on_the_next_call(qapp, tmp_path, monkeypatch) -> None:
    # Regression test: a video whose extraction fails never gets a cache
    # file written, so every later refresh_playlist() -- which fires on
    # nearly every mutating action -- used to re-queue the same doomed
    # ffmpeg run. With 289 videos that was self-perpetuating: the storm was
    # slow enough that the cache never filled, guaranteeing another storm.
    cache_dir = tmp_path / "cache"
    video = VideoInfo(path=str(tmp_path / "c.mp4"), rel_path="c.mp4")

    attempts = []
    monkeypatch.setattr(
        thumbnail_loader_module,
        "get_or_create_thumbnail",
        lambda path, cache_dir: attempts.append(path) or None,
    )

    loader = ThumbnailLoader()
    results = []
    loader.loaded.connect(lambda rel, path: results.append((rel, path)))

    loader.load_missing([video], str(cache_dir))
    assert _run_event_loop_until(qapp, lambda: len(results) == 1)

    for _ in range(5):
        loader.load_missing([video], str(cache_dir))
    _run_event_loop_until(qapp, lambda: len(attempts) > 1, timeout_ms=300)

    assert attempts == [video.path]
    assert results == [("c.mp4", "")]


def test_already_reported_thumbnail_is_not_rechecked(qapp, tmp_path, monkeypatch) -> None:
    # The cached fast path is cheap but not free (a resolve() + exists() per
    # video), and it runs on the main thread -- it must happen once per
    # video per session, not once per refresh_playlist().
    from vat.media.thumbnails import thumbnail_path

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    video = VideoInfo(path=str(tmp_path / "a.mp4"), rel_path="a.mp4")
    thumbnail_path(video.path, str(cache_dir)).write_bytes(b"fake jpeg")

    loader = ThumbnailLoader()
    results = []
    loader.loaded.connect(lambda rel, path: results.append((rel, path)))

    loader.load_missing([video], str(cache_dir))
    loader.load_missing([video], str(cache_dir))
    loader.load_missing([video], str(cache_dir))

    assert len(results) == 1


def test_worker_pool_is_bounded(qapp, tmp_path, monkeypatch) -> None:
    # Regression test for the real freeze: one fresh thread per uncached
    # video meant 289 Thread.start() calls (each blocking until its thread
    # is running, each immediately forking an ffmpeg subprocess) on the
    # *main* thread -- measured at ~1.5 s per refresh_playlist() against the
    # real project, i.e. a beachball on every "Mark Annotated" click.
    import threading

    cache_dir = tmp_path / "cache"
    videos = [VideoInfo(path=str(tmp_path / f"v{i}.mp4"), rel_path=f"v{i}.mp4") for i in range(50)]

    concurrent = []
    counter = {"live": 0}
    lock = threading.Lock()
    release = threading.Event()

    def _slow_extract(path, cache_dir) -> str:
        with lock:
            counter["live"] += 1
            concurrent.append(counter["live"])
        release.wait(5)
        with lock:
            counter["live"] -= 1
        return "/fake/thumb.jpg"

    monkeypatch.setattr(thumbnail_loader_module, "get_or_create_thumbnail", _slow_extract)

    loader = ThumbnailLoader(max_workers=3)
    loader.load_missing(videos, str(cache_dir))
    try:
        assert _run_event_loop_until(qapp, lambda: len(concurrent) >= 3, timeout_ms=2000)
        assert max(concurrent) == 3  # never more than the pool size, for all 50 videos
    finally:
        release.set()


def test_every_queued_video_is_reported_even_beyond_the_pool_size(qapp, tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache"
    videos = [VideoInfo(path=str(tmp_path / f"v{i}.mp4"), rel_path=f"v{i}.mp4") for i in range(20)]
    monkeypatch.setattr(
        thumbnail_loader_module, "get_or_create_thumbnail", lambda path, cache_dir: "/fake/thumb.jpg"
    )

    loader = ThumbnailLoader(max_workers=2)
    results = []
    loader.loaded.connect(lambda rel, path: results.append(rel))

    loader.load_missing(videos, str(cache_dir))

    assert _run_event_loop_until(qapp, lambda: len(results) == 20)
    assert sorted(results) == sorted(v.rel_path for v in videos)


def test_failed_extraction_is_retried_once_its_delay_has_elapsed(qapp, tmp_path, monkeypatch) -> None:
    # A transient failure (drive briefly unmounted, file still copying in)
    # must heal within the session -- but only after a delay, never on the
    # very next refresh_playlist() call.
    cache_dir = tmp_path / "cache"
    video = VideoInfo(path=str(tmp_path / "t.mp4"), rel_path="t.mp4")
    attempts = []
    outcomes = iter([None, "/fake/thumb.jpg"])
    monkeypatch.setattr(
        thumbnail_loader_module, "get_or_create_thumbnail",
        lambda path, cache_dir: attempts.append(path) or next(outcomes),
    )
    clock = {"now": 1000.0}
    monkeypatch.setattr(thumbnail_loader_module, "_now", lambda: clock["now"])

    loader = ThumbnailLoader()
    results = []
    loader.loaded.connect(lambda rel, path: results.append((rel, path)))

    loader.load_missing([video], str(cache_dir))
    assert _run_event_loop_until(qapp, lambda: len(results) == 1)
    assert results == [("t.mp4", "")]

    loader.load_missing([video], str(cache_dir))  # too soon: not retried
    _run_event_loop_until(qapp, lambda: len(attempts) > 1, timeout_ms=200)
    assert attempts == [video.path]

    clock["now"] += thumbnail_loader_module.RETRY_DELAYS_SECONDS[0] + 1
    loader.load_missing([video], str(cache_dir))
    assert _run_event_loop_until(qapp, lambda: len(results) == 2)
    assert results[1] == ("t.mp4", "/fake/thumb.jpg")

    loader.load_missing([video], str(cache_dir))  # succeeded: never looked at again
    _run_event_loop_until(qapp, lambda: len(attempts) > 2, timeout_ms=200)
    assert attempts == [video.path, video.path]


def test_permanent_failure_is_given_up_on_after_the_retry_budget(qapp, tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache"
    video = VideoInfo(path=str(tmp_path / "p.mp4"), rel_path="p.mp4")
    attempts = []
    monkeypatch.setattr(
        thumbnail_loader_module, "get_or_create_thumbnail", lambda path, cache_dir: attempts.append(path) or None,
    )
    clock = {"now": 0.0}
    monkeypatch.setattr(thumbnail_loader_module, "_now", lambda: clock["now"])

    loader = ThumbnailLoader()
    results = []
    loader.loaded.connect(lambda rel, path: results.append(path))

    budget = len(thumbnail_loader_module.RETRY_DELAYS_SECONDS)
    for i in range(budget + 3):
        loader.load_missing([video], str(cache_dir))
        _run_event_loop_until(qapp, lambda: len(results) == min(i + 1, budget + 1), timeout_ms=1000)
        clock["now"] += 10_000.0  # well past any delay

    assert len(attempts) == budget + 1  # the initial try plus every retry, then nothing


def test_prioritize_moves_visible_rows_to_the_front_of_the_queue(qapp, tmp_path, monkeypatch) -> None:
    import threading

    cache_dir = tmp_path / "cache"
    videos = [VideoInfo(path=str(tmp_path / f"v{i}.mp4"), rel_path=f"v{i}.mp4") for i in range(6)]
    release = threading.Event()
    order = []

    def _extract(path, cache_dir) -> str:
        order.append(path)
        release.wait(5)
        return "/fake/thumb.jpg"

    monkeypatch.setattr(thumbnail_loader_module, "get_or_create_thumbnail", _extract)

    loader = ThumbnailLoader(max_workers=1)
    loader.load_missing(videos, str(cache_dir))
    try:
        assert _run_event_loop_until(qapp, lambda: len(order) == 1, timeout_ms=2000)  # v0 in flight
        loader.prioritize(["v4.mp4", "v5.mp4"])
        assert loader.pending_rel_paths() == ["v4.mp4", "v5.mp4", "v1.mp4", "v2.mp4", "v3.mp4"]
        loader.prioritize(["unknown.mp4"])  # ignored, order preserved
        assert loader.pending_rel_paths() == ["v4.mp4", "v5.mp4", "v1.mp4", "v2.mp4", "v3.mp4"]
    finally:
        release.set()
