from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from vat import __version__, app_settings
from vat.errors import ProjectNotFoundError
from vat.project.project import Project
from vat.runtime_deps import check_runtime_dependencies
from vat.ui.project_dialog import ProjectDialog
from vat.ui.theme import apply_dark_theme, apply_light_theme, apply_theme  # noqa: F401 (re-exported)


def _load_startup_project() -> Project | None:
    last_dir = app_settings.load_last_project_dir()
    if last_dir:
        try:
            return Project.open(last_dir)
        except ProjectNotFoundError:
            pass
    return None


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="vat", description="Video Annotation Tool")
    parser.add_argument("--version", action="version", version=f"vat {__version__}")
    parser.add_argument(
        "--doctor", action="store_true",
        help="print how the app resolves its runtime dependencies (for bug reports) and exit",
    )
    parser.add_argument(
        "project_dir", nargs="?", default=None,
        help="project directory to open (defaults to the last-opened project)",
    )
    # Finder passes `-psn_...` to apps launched from the Dock on older
    # macOS versions; ignore anything unrecognised rather than dying on it.
    args, _unknown = parser.parse_known_args(argv)
    return args


def _check_dependencies_or_explain(parent=None) -> bool:
    """Show a dialog if Homebrew's mpv/ffmpeg aren't installed. Returns
    False when the app can't run at all (no libmpv); True otherwise, after
    at most a warning for the optional tools.
    """
    report = check_runtime_dependencies()
    if report.ok:
        return True
    if report.missing_required:
        QMessageBox.critical(parent, "Missing Required Software", report.message())
        return False
    QMessageBox.warning(parent, "Missing Optional Software", report.message())
    return True


def doctor_report() -> str:
    """Everything a bug report about "no thumbnails" / "won't start" needs:
    where each runtime dependency was (or wasn't) found, and the parts of
    the environment that have bitten before (PATH, any DYLD_* variable --
    see _mpv_bootstrap.libmpv_discoverable()). Pure: no Qt, no dialogs.
    """
    import os
    import platform

    from vat.media.tools import find_tool
    from vat.playback._mpv_bootstrap import locate_libmpv

    lines = [
        f"vat {__version__}",
        f"python {platform.python_version()} ({sys.executable})",
        f"platform {platform.platform()} {platform.machine()}",
        f"frozen {getattr(sys, 'frozen', False)}",
        f"libmpv {locate_libmpv() or 'NOT FOUND'}",
    ]
    for tool in ("ffmpeg", "ffprobe"):
        lines.append(f"{tool} {find_tool(tool) or 'NOT FOUND'}")
    lines.append(f"PATH {os.environ.get('PATH', '')}")
    dyld = {k: v for k, v in os.environ.items() if k.startswith("DYLD_")}
    lines.append(f"DYLD_* {dyld if dyld else 'none (good)'}")
    report = check_runtime_dependencies()
    lines.append("dependencies " + ("ok" if report.ok else report.message().replace(chr(10), " ")))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if args.doctor:
        print(doctor_report())
        return 0
    app = QApplication(sys.argv)
    apply_theme(app, app_settings.load_theme())

    # Checked *before* importing MainWindow: that import chain reaches
    # `import mpv`, whose module body dlopen()s libmpv and raises if it
    # isn't there -- an unhelpful traceback for a user who just hasn't
    # run `brew install mpv` yet.
    if not _check_dependencies_or_explain():
        return 1
    from vat.ui.main_window import MainWindow

    project: Project | None = None
    if args.project_dir:
        try:
            project = Project.open(args.project_dir)
        except ProjectNotFoundError as exc:
            QMessageBox.warning(None, "Cannot Open Project", str(exc))
    if project is None:
        project = _load_startup_project()
    if project is None:
        dialog = ProjectDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.project is None:
            return 0
        project = dialog.project

    app_settings.save_last_project_dir(project.config.project_dir)

    window = MainWindow(project)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
