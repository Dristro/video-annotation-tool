from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog

from vat import app_settings
from vat.errors import ProjectNotFoundError
from vat.project.project import Project
from vat.ui.main_window import MainWindow
from vat.ui.project_dialog import ProjectDialog


def apply_dark_theme(app: QApplication) -> None:
    """Dark palette in the DaVinci-Resolve-ish spirit of the rest of the
    layout (BACKLOG.md: the arrangement already matches, the styling
    didn't). "Fusion" is Qt's own cross-platform style -- it's the one
    that actually honors a custom QPalette; the native macOS style mostly
    ignores palette colors and follows the OS appearance instead, which
    would make this a no-op on macOS otherwise. Deliberately unconditional
    (no light/dark toggle) -- not asked for, and one hardcoded palette is
    simpler than a theme-switching mechanism nothing else needs yet.
    Custom-painted widgets (e.g. TimelineWidget's track/cut colors) draw
    with their own QPainter colors regardless of palette, by design --
    those are a separate, deliberate visual language (cut label colors
    have to stay legible against many different backgrounds via
    utils.colors, not just this one).
    """
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 48))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 48))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(45, 45, 48))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 80, 80))
    palette.setColor(QPalette.ColorRole.Link, QColor(100, 160, 220))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(70, 130, 180))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(120, 120, 120))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(120, 120, 120))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(120, 120, 120))
    app.setPalette(palette)


def _load_startup_project() -> Project | None:
    last_dir = app_settings.load_last_project_dir()
    if last_dir:
        try:
            return Project.open(last_dir)
        except ProjectNotFoundError:
            pass
    return None


def main() -> int:
    app = QApplication(sys.argv)
    apply_dark_theme(app)

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
