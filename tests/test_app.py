import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.app import apply_dark_theme  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_apply_dark_theme_sets_dark_window_color(qapp):
    apply_dark_theme(qapp)
    window_color = qapp.palette().color(QPalette.ColorRole.Window)
    # Dark, not the default light-gray Qt window color.
    assert window_color.lightness() < 128


def test_apply_dark_theme_keeps_text_readable(qapp):
    apply_dark_theme(qapp)
    text_color = qapp.palette().color(QPalette.ColorRole.WindowText)
    window_color = qapp.palette().color(QPalette.ColorRole.Window)
    assert text_color.lightness() > window_color.lightness()
