import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from vat.media.video_scanner import VideoInfo  # noqa: E402
from vat.playback import thumbnail_loader as thumbnail_loader_module  # noqa: E402
from vat.playback.thumbnail_loader import ThumbnailLoader  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


def _run_event_loop_until(qapp, predicate, timeout_ms=5000):
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
    return False


def test_already_cached_thumbnail_emitted_immediately_without_extraction(qapp, tmp_path, monkeypatch):
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


def test_missing_thumbnail_extracted_in_background_and_emitted(qapp, tmp_path, monkeypatch):
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


def test_extraction_failure_emits_empty_string(qapp, tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    video = VideoInfo(path=str(tmp_path / "c.mp4"), rel_path="c.mp4")

    monkeypatch.setattr(thumbnail_loader_module, "get_or_create_thumbnail", lambda path, cache_dir: None)

    loader = ThumbnailLoader()
    results = []
    loader.loaded.connect(lambda rel, path: results.append((rel, path)))

    loader.load_missing([video], str(cache_dir))

    assert _run_event_loop_until(qapp, lambda: len(results) == 1)
    assert results[0] == ("c.mp4", "")
