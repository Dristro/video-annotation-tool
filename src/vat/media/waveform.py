from __future__ import annotations

import hashlib
import json
import struct
import subprocess
from pathlib import Path

# ffmpeg decodes the audio track down to this coarse a mono sample rate --
# not the final resolution shown, just cheap enough to decode and pipe
# through stdout without pulling the whole track into memory at full rate.
DECODE_SAMPLE_RATE_HZ = 200
# Final peak count regardless of video length, so a 2-minute and a
# 20-minute video both render at the same visual resolution across
# TimelineWidget's full width.
WAVEFORM_BUCKETS = 400


def waveform_path(video_path: str, cache_dir: str) -> Path:
    """Deterministic cache path for `video_path`'s waveform, keyed by its
    resolved path -- same pattern as media.thumbnails.thumbnail_path.
    """
    digest = hashlib.sha1(str(Path(video_path).resolve()).encode("utf-8")).hexdigest()
    return Path(cache_dir) / f"{digest}.json"


def get_or_create_waveform(video_path: str, cache_dir: str) -> list[float] | None:
    """Return up to WAVEFORM_BUCKETS peak amplitudes (each in [0.0, 1.0])
    for `video_path`'s audio track, decoding via ffmpeg and caching to
    disk as JSON the first time -- later calls just read the cache file.
    None if extraction fails (no audio track, ffmpeg not installed, not a
    real video, etc.) -- best-effort, same spirit as media.thumbnails and
    Preloader; callers must treat None as "no waveform to show", not an
    error.
    """
    out_path = waveform_path(video_path, cache_dir)
    if out_path.exists():
        try:
            return json.loads(out_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass  # cache file corrupt/unreadable -- fall through and regenerate
    peaks = _extract_peaks(video_path)
    if peaks is None:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(peaks))
    return peaks


def _extract_peaks(video_path: str) -> list[float] | None:
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-i", video_path,
                "-vn", "-ac", "1", "-ar", str(DECODE_SAMPLE_RATE_HZ),
                "-f", "s16le", "pipe:1",
            ],
            capture_output=True,
            timeout=30,
            check=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None
    raw = result.stdout
    sample_count = len(raw) // 2  # 16-bit samples
    if sample_count == 0:
        return None
    samples = struct.unpack(f"<{sample_count}h", raw[: sample_count * 2])
    bucket_size = max(1, sample_count // WAVEFORM_BUCKETS)
    peaks = []
    for i in range(0, sample_count, bucket_size):
        chunk = samples[i:i + bucket_size]
        if not chunk:
            continue
        peaks.append(min(1.0, max(abs(s) for s in chunk) / 32768.0))
    return peaks
