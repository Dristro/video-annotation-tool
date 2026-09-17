from __future__ import annotations

import json
import os
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


def list_videos(videos_dir: str, recursive: bool = False) -> list[VideoInfo]:
    """Return all supported video files under `videos_dir`, sorted by
    relative path (case-insensitive).

    By default only top-level files are scanned: a "videos directory" is
    treated as a flat playlist source, matching the "move through all
    videos in dir like a playlist" requirement. With `recursive=True`
    subfolders are walked too (a per-project setting, see
    `ProjectConfig.recursive_scan`); a nested video's `rel_path` is then
    its path relative to `videos_dir` with forward slashes
    (`"day1/cam2/clip.mp4"`), which is also the key it gets in
    `annotations.json` -- so the same file keeps the same annotations
    whether or not the option is on, and the file stays portable across
    platforms. Hidden files and directories (dot-prefixed) are skipped in
    both modes.
    """
    base = Path(videos_dir)
    if not base.is_dir():
        return []
    entries = []
    if recursive:
        for root, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for filename in filenames:
                child = Path(root) / filename
                if _is_video_file(child):
                    entries.append(VideoInfo(path=str(child), rel_path=child.relative_to(base).as_posix()))
    else:
        for child in base.iterdir():
            if _is_video_file(child):
                entries.append(VideoInfo(path=str(child), rel_path=child.name))
    entries.sort(key=lambda v: v.rel_path.lower())
    return entries


def _is_video_file(path: Path) -> bool:
    return path.is_file() and not path.name.startswith(".") and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS


def rel_path_for(videos_dir: str, video_path: str) -> str:
    # as_posix() so a nested video's key in annotations.json is the same
    # on every platform (and matches list_videos()'s rel_path exactly).
    return Path(video_path).resolve().relative_to(Path(videos_dir).resolve()).as_posix()


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
