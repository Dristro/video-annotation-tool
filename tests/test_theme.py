import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.ui.theme import apply_dark_theme, apply_light_theme, apply_theme  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_apply_dark_theme_sets_dark_window_color(qapp):
    apply_dark_theme(qapp)
    window_color = qapp.palette().color(QPalette.ColorRole.Window)
    assert window_color.lightness() < 128


def test_apply_dark_theme_keeps_text_readable(qapp):
    apply_dark_theme(qapp)
    text_color = qapp.palette().color(QPalette.ColorRole.WindowText)
    window_color = qapp.palette().color(QPalette.ColorRole.Window)
    assert text_color.lightness() > window_color.lightness()


def test_apply_light_theme_sets_light_window_color(qapp):
    apply_light_theme(qapp)
    window_color = qapp.palette().color(QPalette.ColorRole.Window)
    assert window_color.lightness() >= 128


def test_switching_between_themes_fully_replaces_palette(qapp):
    apply_dark_theme(qapp)
    dark_window_color = qapp.palette().color(QPalette.ColorRole.Window)

    apply_light_theme(qapp)
    light_window_color = qapp.palette().color(QPalette.ColorRole.Window)

    assert dark_window_color != light_window_color

    apply_dark_theme(qapp)
    assert qapp.palette().color(QPalette.ColorRole.Window) == dark_window_color


def test_apply_theme_dispatches_to_light(qapp):
    apply_theme(qapp, "light")
    assert qapp.palette().color(QPalette.ColorRole.Window).lightness() >= 128


def test_apply_theme_dispatches_to_dark(qapp):
    apply_theme(qapp, "dark")
    assert qapp.palette().color(QPalette.ColorRole.Window).lightness() < 128


def test_apply_theme_unknown_value_falls_back_to_dark(qapp):
    apply_theme(qapp, "not-a-real-theme")
    assert qapp.palette().color(QPalette.ColorRole.Window).lightness() < 128
