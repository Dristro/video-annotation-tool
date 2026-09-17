from typing import Callable
from PySide6.QtCore import QCoreApplication
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from vat.playback import waveform_loader as waveform_loader_module  # noqa: E402
from vat.playback.waveform_loader import WaveformLoader  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def _run_event_loop_until(qapp, predicate: Callable[[], bool], timeout_ms=5000) -> bool:
    import time

    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
    return False


def test_load_emits_loaded_with_peaks(qapp, monkeypatch) -> None:
    monkeypatch.setattr(waveform_loader_module, "get_or_create_waveform", lambda path, cache_dir: [0.1, 0.2])

    loader = WaveformLoader()
    results = []
    loader.loaded.connect(lambda path, peaks: results.append((path, peaks)))

    loader.load("/videos/a.mp4", "/cache")

    assert _run_event_loop_until(qapp, lambda: len(results) == 1)
    assert results[0] == ("/videos/a.mp4", [0.1, 0.2])


def test_load_emits_empty_list_when_extraction_fails(qapp, monkeypatch) -> None:
    monkeypatch.setattr(waveform_loader_module, "get_or_create_waveform", lambda path, cache_dir: None)

    loader = WaveformLoader()
    results = []
    loader.loaded.connect(lambda path, peaks: results.append((path, peaks)))

    loader.load("/videos/broken.mp4", "/cache")

    assert _run_event_loop_until(qapp, lambda: len(results) == 1)
    assert results[0] == ("/videos/broken.mp4", [])


def test_rapid_requests_only_decode_the_in_flight_and_the_latest(qapp, monkeypatch) -> None:
    # Regression guard for rapid playlist stepping: every skipped-over
    # video used to get a full audio decode on its own thread. Now the
    # intermediate requests are dropped before they ever start.
    import threading

    started = []
    release = threading.Event()

    def _slow(path, cache_dir):
        started.append(path)
        release.wait(5)
        return [0.5]

    monkeypatch.setattr(waveform_loader_module, "get_or_create_waveform", _slow)

    loader = WaveformLoader()
    results = []
    loader.loaded.connect(lambda path, peaks: results.append(path))

    for name in ("a", "b", "c", "d", "e"):
        loader.load(f"/videos/{name}.mp4", "/cache")
    assert _run_event_loop_until(qapp, lambda: len(started) == 1, timeout_ms=2000)
    release.set()

    assert _run_event_loop_until(qapp, lambda: len(results) == 2)
    assert started == ["/videos/a.mp4", "/videos/e.mp4"]
    assert results == ["/videos/a.mp4", "/videos/e.mp4"]


def test_worker_exits_and_restarts_cleanly_between_requests(qapp, monkeypatch) -> None:
    monkeypatch.setattr(waveform_loader_module, "get_or_create_waveform", lambda path, cache_dir: [0.1])
    loader = WaveformLoader()
    results = []
    loader.loaded.connect(lambda path, peaks: results.append(path))

    loader.load("/videos/a.mp4", "/cache")
    assert _run_event_loop_until(qapp, lambda: len(results) == 1)
    loader.load("/videos/b.mp4", "/cache")
    assert _run_event_loop_until(qapp, lambda: len(results) == 2)
    assert results == ["/videos/a.mp4", "/videos/b.mp4"]
