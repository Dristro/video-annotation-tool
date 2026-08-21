import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor  # noqa: E402

from vat.utils.colors import color_for_label, contrasting_text_color  # noqa: E402


def test_color_for_label_is_deterministic():
    assert color_for_label("goal") == color_for_label("goal")


def test_color_for_label_empty_is_gray():
    assert color_for_label("") == QColor("#7f7f7f")


def test_contrasting_text_color_dark_background_gets_white_text():
    assert contrasting_text_color(QColor("#000075")) == QColor("white")  # dark navy


def test_contrasting_text_color_light_background_gets_black_text():
    assert contrasting_text_color(QColor("#bcf60c")) == QColor("black")  # bright yellow-green
    assert contrasting_text_color(QColor("#fabebe")) == QColor("black")  # light pink


def test_contrasting_text_color_covers_whole_palette_legibly():
    # Every palette color must resolve to *some* readable choice -- this is
    # really a regression guard that the formula doesn't raise/return
    # something odd for any of the actual colors in use.
    from vat.utils.colors import _PALETTE

    for hex_code in _PALETTE:
        result = contrasting_text_color(QColor(hex_code))
        assert result in (QColor("black"), QColor("white"))
