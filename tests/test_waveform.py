import struct
import subprocess

from vat.media.waveform import DECODE_SAMPLE_RATE_HZ, get_or_create_waveform, waveform_path


def _fake_pcm_bytes(seconds: float, amplitude: int = 16000) -> bytes:
    sample_count = int(seconds * DECODE_SAMPLE_RATE_HZ)
    return struct.pack(f"<{sample_count}h", *([amplitude] * sample_count))


def test_waveform_path_deterministic_for_same_video(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    cache_dir = tmp_path / "cache"

    assert waveform_path(str(video), str(cache_dir)) == waveform_path(str(video), str(cache_dir))


def test_get_or_create_waveform_returns_none_when_extraction_fails(tmp_path):
    video = tmp_path / "not-a-real-video.mp4"
    video.write_bytes(b"not a real video, just bytes")
    cache_dir = tmp_path / "cache"

    assert get_or_create_waveform(str(video), str(cache_dir)) is None


def test_get_or_create_waveform_extracts_and_caches(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    cache_dir = tmp_path / "cache"
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=_fake_pcm_bytes(2.0))

    monkeypatch.setattr(subprocess, "run", fake_run)

    first = get_or_create_waveform(str(video), str(cache_dir))
    assert first is not None
    assert all(0.0 <= p <= 1.0 for p in first)
    assert len(calls) == 1

    second = get_or_create_waveform(str(video), str(cache_dir))
    assert second == first
    assert len(calls) == 1  # cached -- ffmpeg not invoked again


def test_get_or_create_waveform_peaks_reflect_amplitude(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    cache_dir = tmp_path / "cache"

    def fake_run(cmd, **kwargs):
        # Half max amplitude (16384 / 32768).
        return subprocess.CompletedProcess(cmd, 0, stdout=_fake_pcm_bytes(1.0, amplitude=16384))

    monkeypatch.setattr(subprocess, "run", fake_run)

    peaks = get_or_create_waveform(str(video), str(cache_dir))

    assert all(p == 0.5 for p in peaks)


def test_get_or_create_waveform_regenerates_on_corrupt_cache(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    cache_dir = tmp_path / "cache"
    out_path = waveform_path(str(video), str(cache_dir))
    out_path.parent.mkdir(parents=True)
    out_path.write_text("not valid json {{{")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=_fake_pcm_bytes(1.0))

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = get_or_create_waveform(str(video), str(cache_dir))

    assert result is not None
    assert len(calls) == 1
