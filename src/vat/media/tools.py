"""Locate the external command-line tools the app shells out to.

Every subprocess call in the codebase (`ffmpeg` for thumbnails/waveforms,
`ffprobe` for durations) goes through `tool_path()` rather than passing a
bare command name to `subprocess.run()`. A bare name relies on `PATH`,
and **an app launched from Finder/the Dock does not get the user's shell
`PATH`** -- it gets launchd's minimal default (`/usr/bin:/bin:/usr/sbin:
/sbin`), which never includes Homebrew's `/opt/homebrew/bin`. Running
`vat` from a Terminal worked; the very same code inside the `.app` bundle
silently found no ffmpeg at all, and since thumbnails/waveforms/durations
are all deliberately best-effort, nothing said so (exactly the failure
shape of the `DYLD_LIBRARY_PATH` landmine in `_mpv_bootstrap.py`).

Resolution order, first hit wins, cached per process:

1. `VAT_<TOOL>` environment variable (e.g. `VAT_FFMPEG=/some/ffmpeg`),
   an explicit override for unusual installs and for later Linux
   packaging.
2. `shutil.which()` -- whatever the current `PATH` says.
3. The well-known Homebrew prefixes (`/opt/homebrew/bin` on Apple
   Silicon, `/usr/local/bin` on Intel Macs), even when not on `PATH`.
"""

from __future__ import annotations

import os
import shutil

KNOWN_BIN_DIRS = ("/opt/homebrew/bin", "/usr/local/bin")

_cache: dict[str, str | None] = {}


def find_tool(name: str) -> str | None:
    """Absolute path to the `name` executable, or None if it can't be
    found anywhere we know to look.
    """
    if name in _cache:
        return _cache[name]
    found: str | None = None
    override = os.environ.get(f"VAT_{name.upper()}")
    if override and _is_executable(override):
        found = override
    if found is None:
        found = shutil.which(name)
    if found is None:
        for bin_dir in KNOWN_BIN_DIRS:
            candidate = os.path.join(bin_dir, name)
            if _is_executable(candidate):
                found = candidate
                break
    _cache[name] = found
    return found


def tool_path(name: str) -> str:
    """`find_tool()`, falling back to the bare name so callers can still
    hand it to `subprocess.run()` -- which then fails with
    `FileNotFoundError`, the exact exception every best-effort caller
    already treats as "not available".
    """
    return find_tool(name) or name


def clear_cache() -> None:
    """Forget resolved paths (tests, or after the user installs a tool
    mid-session and retries)."""
    _cache.clear()


def _is_executable(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)
