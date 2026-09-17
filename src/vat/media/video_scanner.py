from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from vat.constants import SUPPORTED_VIDEO_EXTENSIONS
from vat.media.tools import tool_path


@dataclass
class VideoInfo:
    path: str
    rel_path: str
    duration: float | None = None


def list_videos(videos_dir: str) -> list[VideoInfo]:
    """Return all supported video files directly under `videos_dir`, sorted by name.

    Only top-level files are scanned (a "videos directory" is treated as a flat
    playlist source, matching the "move through all videos in dir like a
    playlist" requirement).
    """
    base = Path(videos_dir)
    if not base.is_dir():
        return []
    entries = []
    for child in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        if child.is_file() and child.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
            entries.append(VideoInfo(path=str(child), rel_path=child.name))
    return entries


def rel_path_for(videos_dir: str, video_path: str) -> str:
    return str(Path(video_path).resolve().relative_to(Path(videos_dir).resolve()))


_duration_cache: dict[str, float] = {}


def probe_duration(video_path: str) -> float | None:
    """Return video duration in seconds via ffprobe, or None if it can't be determined.

    Results are cached in-process since probing spawns a subprocess per call.
    """
    cached = _duration_cache.get(video_path)
    if cached is not None:
        return cached
    try:
        result = subprocess.run(
            [
                tool_path("ffprobe"),
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None
    try:
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return None
    _duration_cache[video_path] = duration
    return duration
