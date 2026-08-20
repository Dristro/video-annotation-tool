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
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os

_bootstrapped = False


def ensure_libmpv_loadable() -> None:
    global _bootstrapped
    if _bootstrapped:
        return
    _bootstrapped = True

    if ctypes.util.find_library("mpv") is not None:
        return  # already discoverable and (presumably) loadable as-is

    for lib_dir in ("/opt/homebrew/lib", "/usr/local/lib"):
        candidate = os.path.join(lib_dir, "libmpv.dylib")
        if os.path.exists(candidate):
            os.environ["DYLD_LIBRARY_PATH"] = os.pathsep.join(
                filter(None, [os.environ.get("DYLD_LIBRARY_PATH", ""), lib_dir])
            )
            ctypes.CDLL(candidate, mode=os.RTLD_LAZY | os.RTLD_GLOBAL)
            return
