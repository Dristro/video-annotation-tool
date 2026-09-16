import threading

from vat.playback.preloader import Preloader


def test_preload_reads_file_without_error(tmp_path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x" * 1000)

    preloader = Preloader()
    preloader.preload(str(video))
    preloader._thread.join(timeout=5)

    assert not preloader._thread.is_alive()


def test_preload_missing_file_does_not_raise(tmp_path) -> None:
    preloader = Preloader()
    preloader.preload(str(tmp_path / "does-not-exist.mp4"))
    preloader._thread.join(timeout=5)

    assert not preloader._thread.is_alive()


def test_preload_skips_when_already_in_flight(tmp_path, monkeypatch) -> None:
    # Only the *next* queued video is ever worth warming -- a second
    # preload() call while one is still running must be a no-op, not
    # queued behind the first (Preloader's docstring/CLAUDE.md).
    started = threading.Event()
    release = threading.Event()
    calls = []

    def fake_run(path) -> None:
        calls.append(path)
        started.set()
        release.wait(timeout=5)

    monkeypatch.setattr(Preloader, "_run", staticmethod(fake_run))

    preloader = Preloader()
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x" * 100)

    preloader.preload(str(video))
    assert started.wait(timeout=5)

    preloader.preload(str(video))  # should be skipped -- first is still in flight

    release.set()
    preloader._thread.join(timeout=5)
    assert calls == [str(video)]


def test_preload_allows_new_call_once_previous_finished(tmp_path) -> None:
    preloader = Preloader()
    video_a = tmp_path / "a.mp4"
    video_a.write_bytes(b"x" * 100)
    video_b = tmp_path / "b.mp4"
    video_b.write_bytes(b"y" * 100)

    preloader.preload(str(video_a))
    preloader._thread.join(timeout=5)
    first_thread = preloader._thread

    preloader.preload(str(video_b))
    preloader._thread.join(timeout=5)

    assert preloader._thread is not first_thread
