from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from vat.media.tools import tool_path

THUMBNAIL_WIDTH = 120
THUMBNAIL_TIMESTAMP_SECONDS = 1.0


def thumbnail_path(video_path: str, cache_dir: str) -> Path:
    """Deterministic cache path for `video_path`'s thumbnail, keyed by its
    resolved path so the same video always maps to the same file.
    """
    digest = hashlib.sha1(str(Path(video_path).resolve()).encode("utf-8")).hexdigest()
    return Path(cache_dir) / f"{digest}.jpg"


def get_or_create_thumbnail(video_path: str, cache_dir: str) -> str | None:
    """Return a path to a small JPEG thumbnail for `video_path`, extracting
    and caching it under `cache_dir` the first time it's asked for --
    later calls just check the file exists. None if extraction fails (not
    a real video, ffmpeg not installed, etc.) -- best-effort, same spirit
    as Preloader; nothing calling this should treat None as an error.
    """
    out_path = thumbnail_path(video_path, cache_dir)
    if out_path.exists():
        return str(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                tool_path("ffmpeg"), "-y",
                "-ss", str(THUMBNAIL_TIMESTAMP_SECONDS),
                "-i", video_path,
                "-frames:v", "1",
                "-vf", f"scale={THUMBNAIL_WIDTH}:-1",
                str(out_path),
            ],
            capture_output=True,
            timeout=10,
            check=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None
    return str(out_path) if out_path.exists() else None
