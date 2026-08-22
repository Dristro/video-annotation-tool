import subprocess
from pathlib import Path

from vat.media.thumbnails import get_or_create_thumbnail, thumbnail_path


def test_thumbnail_path_deterministic_for_same_video(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    cache_dir = tmp_path / "cache"

    assert thumbnail_path(str(video), str(cache_dir)) == thumbnail_path(str(video), str(cache_dir))


def test_thumbnail_path_differs_for_different_videos(tmp_path):
    cache_dir = tmp_path / "cache"
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"

    assert thumbnail_path(str(a), str(cache_dir)) != thumbnail_path(str(b), str(cache_dir))


def test_get_or_create_thumbnail_returns_none_when_extraction_fails(tmp_path):
    # Not a real video -- ffmpeg (if installed) will fail on it; if ffmpeg
    # isn't installed at all, FileNotFoundError is caught the same way.
    # Either way this must degrade gracefully, never raise.
    video = tmp_path / "not-a-real-video.mp4"
    video.write_bytes(b"not a real video, just bytes")
    cache_dir = tmp_path / "cache"

    result = get_or_create_thumbnail(str(video), str(cache_dir))

    assert result is None


def test_get_or_create_thumbnail_uses_cache_on_second_call(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    cache_dir = tmp_path / "cache"
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        # Simulate ffmpeg actually producing the output file -- the real
        # output path is the last argument passed to ffmpeg.
        Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(cmd[-1]).write_bytes(b"fake jpeg bytes")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    first = get_or_create_thumbnail(str(video), str(cache_dir))
    assert first is not None
    assert len(calls) == 1

    second = get_or_create_thumbnail(str(video), str(cache_dir))
    assert second == first
    assert len(calls) == 1  # cached -- ffmpeg not invoked again
