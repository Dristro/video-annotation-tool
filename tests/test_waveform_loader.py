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
