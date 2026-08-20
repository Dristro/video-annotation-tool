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
