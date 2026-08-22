from __future__ import annotations

import hashlib

from PySide6.QtGui import QColor

# A small fixed palette (rather than fully random HSV) so label colors stay
# legible and visually distinct on both the timeline and playlist badges.
_PALETTE = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080",
    "#e6beff", "#9a6324", "#800000", "#808000", "#000075",
]


def color_for_label(label: str) -> QColor:
    if not label:
        return QColor("#7f7f7f")
    digest = hashlib.sha1(label.encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(_PALETTE)
    return QColor(_PALETTE[index])


def contrasting_text_color(background: QColor) -> QColor:
    """Black or white, whichever reads better on `background`.

    Several palette entries (e.g. the light yellow-green, pink, lavender)
    are too light for hardcoded white label text to stay readable -- this
    picks based on perceptual luminance (YIQ formula) instead of assuming
    a dark background every time.
    """
    yiq = (background.red() * 299 + background.green() * 587 + background.blue() * 114) / 1000
    return QColor("black") if yiq >= 128 else QColor("white")
