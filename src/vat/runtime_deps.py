"""Startup check for the system tools the app can't ship itself.

The `.app` bundle deliberately does *not* embed libmpv/ffmpeg (see
`packaging/README.md`): they come from Homebrew, the same way they do for
a from-source install. That makes "is it actually installed?" a runtime
question, and the answer has to be a dialog the user can act on -- not an
`ImportError` from python-mpv's module body (libmpv) or, worse, silently
missing thumbnails/waveforms/durations (ffmpeg/ffprobe, which every
caller treats as best-effort).

`check_runtime_dependencies()` is pure (no Qt) so it's unit-testable and
usable from the CLI; `vat.app.main()` turns its result into the dialog.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vat.media.tools import find_tool
from vat.playback._mpv_bootstrap import locate_libmpv

INSTALL_HINT = "brew install mpv ffmpeg"


@dataclass
class DependencyReport:
    missing_required: list[str] = field(default_factory=list)  # can't run at all without these
    missing_optional: list[str] = field(default_factory=list)  # degraded features only

    @property
    def ok(self) -> bool:
        return not self.missing_required and not self.missing_optional

    def message(self) -> str:
        """Human-readable explanation suitable for a dialog body."""
        parts = []
        if self.missing_required:
            parts.append(
                "Video playback needs " + ", ".join(self.missing_required)
                + ", which could not be found. The app cannot start without it."
            )
        if self.missing_optional:
            parts.append(
                ", ".join(self.missing_optional) + " could not be found. The app will run, but "
                "playlist thumbnails, the audio waveform and video durations won't be available."
            )
        parts.append(f"Install the missing tools with Homebrew (https://brew.sh):\n\n    {INSTALL_HINT}")
        return "\n\n".join(parts)


def check_runtime_dependencies() -> DependencyReport:
    report = DependencyReport()
    if locate_libmpv() is None:
        report.missing_required.append("libmpv (the `mpv` Homebrew package)")
    for tool in ("ffmpeg", "ffprobe"):
        if find_tool(tool) is None:
            report.missing_optional.append(tool)
    return report
