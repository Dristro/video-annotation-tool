"""Must be imported before `import mpv` anywhere in this codebase.

On this machine (macOS Tahoe 26.2, Apple Silicon), the system
OpenGL.framework no longer exports `_CGLGetCurrentContext`, a symbol
Homebrew's libmpv still references from an unused legacy Cocoa/OpenGL code
path. `ctypes.CDLL` opens libraries with eager symbol resolution
(RTLD_NOW), which fails outright on that missing symbol -- even though
running `mpv` as a normal process works fine, because normal process
loading binds that unused symbol lazily and never resolves it (mpv's
actual video output is Vulkan/libplacebo, not legacy OpenGL).

The fix: pre-load libmpv ourselves with RTLD_LAZY before python-mpv's own
`ctypes.CDLL(sofile)` call runs. Once a library is already loaded in the
process, a subsequent `dlopen` on the same path just bumps mpv's refcount
and returns the existing (successfully lazy-loaded) handle instead of
redoing eager resolution.

Also works around `ctypes.util.find_library('mpv')` returning None for
Homebrew-installed libs that live outside the default dyld search paths.
That part needs `DYLD_LIBRARY_PATH` set -- and setting it *must* be scoped
to the `import mpv` that needs it, see `libmpv_discoverable()` below.
"""

from __future__ import annotations

import contextlib
import ctypes
import ctypes.util
import os

DYLD_LIBRARY_PATH = "DYLD_LIBRARY_PATH"

_bootstrapped = False
_lib_dir: str | None = None

# Where Homebrew puts libmpv on Apple Silicon and on Intel Macs, in that
# order. Shared with `locate_libmpv()` so the startup dependency check
# (vat/runtime_deps.py) and the actual loader can't disagree about where
# to look.
KNOWN_LIB_DIRS = ("/opt/homebrew/lib", "/usr/local/lib")


def locate_libmpv() -> str | None:
    """Path to a libmpv the process could load, or None. Does *not* load
    it -- this is what the startup dependency check calls so a missing
    `brew install mpv` can be reported in a dialog instead of surfacing as
    an ImportError from deep inside python-mpv.
    """
    found = ctypes.util.find_library("mpv")
    if found is not None:
        return found
    for lib_dir in KNOWN_LIB_DIRS:
        candidate = os.path.join(lib_dir, "libmpv.dylib")
        if os.path.exists(candidate):
            return candidate
    return None


def ensure_libmpv_loadable() -> None:
    global _bootstrapped, _lib_dir
    if _bootstrapped:
        return
    _bootstrapped = True

    if ctypes.util.find_library("mpv") is not None:
        return  # already discoverable and (presumably) loadable as-is

    for lib_dir in KNOWN_LIB_DIRS:
        candidate = os.path.join(lib_dir, "libmpv.dylib")
        if os.path.exists(candidate):
            ctypes.CDLL(candidate, mode=os.RTLD_LAZY | os.RTLD_GLOBAL)
            _lib_dir = lib_dir
            return


@contextlib.contextmanager
def libmpv_discoverable():
    """Put the Homebrew lib dir on `DYLD_LIBRARY_PATH` for the duration of
    the block, then put the variable back exactly as it was.

    python-mpv's module body does `CDLL(ctypes.util.find_library('mpv'))`,
    and `find_library` returns None for Homebrew libs unless that variable
    points at them -- so `import mpv` genuinely needs it. But it must not
    outlive the import, which is what this restores.

    **Leaving `DYLD_LIBRARY_PATH` set process-wide silently breaks every
    `ffmpeg`/`ffprobe` subprocess the app spawns**, which is not obvious
    and cost a real debugging session to pin down. Child processes inherit
    it, and any `DYLD_*` variable makes dyld drop its shared-cache /
    prebuilt-loader fast path and bind far more eagerly -- which turns
    ffmpeg's *own* unused, normally-never-resolved reference to the same
    missing `_CGLGetCurrentContext` symbol (from `libavfilter`, which links
    legacy OpenGL) into a hard `dyld` abort before `main()` runs. Exactly
    the same OS/library interaction described above for libmpv, one level
    down. Symptom, on this project's real 289-video library: **every**
    thumbnail, waveform and duration probe failed instantly and silently
    (all three are written to treat failure as "not available" rather than
    an error), so no thumbnail was ever cached -- and because the playlist
    re-queued every uncached video on each refresh, the app kept
    re-launching a doomed extraction for all 289 of them on every single
    "Mark Annotated" click. Verified directly: the same ffmpeg command
    succeeds with the variable unset and aborts with it set.
    """
    if _lib_dir is None:
        yield
        return
    previous = os.environ.get(DYLD_LIBRARY_PATH)
    os.environ[DYLD_LIBRARY_PATH] = os.pathsep.join(filter(None, [previous or "", _lib_dir]))
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(DYLD_LIBRARY_PATH, None)
        else:
            os.environ[DYLD_LIBRARY_PATH] = previous
