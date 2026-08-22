from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Lives here (not in app.py) specifically so MainWindow can import it to
# apply a theme change live from the View menu without creating a circular
# import -- app.py already imports MainWindow, so MainWindow importing
# back from app.py would be circular.

THEMES = ("dark", "light")
DEFAULT_THEME = "dark"


def apply_dark_theme(app: QApplication) -> None:
    """Dark palette in the DaVinci-Resolve-ish spirit of the rest of the
    layout (BACKLOG.md: the arrangement already matches, the styling
    didn't). "Fusion" is Qt's own cross-platform style -- it's the one
    that actually honors a custom QPalette; the native macOS style mostly
    ignores palette colors and follows the OS appearance instead, which
    would make this a no-op on macOS otherwise.
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


def apply_light_theme(app: QApplication) -> None:
    """Light palette -- still under Fusion (not the native style) so
    switching back and forth between this and apply_dark_theme() is a full,
    deterministic palette replacement each time with no leftover roles from
    whichever theme was active before. A freshly-constructed QPalette()
    already *is* Qt's own light default, so there's nothing to hand-pick
    here the way there was for dark.
    """
    app.setStyle("Fusion")
    app.setPalette(QPalette())


def apply_theme(app: QApplication, theme: str) -> None:
    """Anything other than exactly "light" is treated as dark -- a safe,
    unsurprising fallback if a stored preference is ever missing or
    corrupted, without needing separate validation.
    """
    if theme == "light":
        apply_light_theme(app)
    else:
        apply_dark_theme(app)
