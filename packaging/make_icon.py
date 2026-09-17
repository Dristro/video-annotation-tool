#!/usr/bin/env python3
"""Draw the app icon with Qt and emit an .icns (macOS) from it.

No binary icon asset is checked in: the icon is a few shapes (a dark
rounded tile, a film-strip edge, a play mark bracketed by in/out cut
marks), so generating it at build time keeps the repo free of opaque
blobs and makes the design editable in code. `iconutil` (ships with
macOS) turns the PNG set into the .icns the bundle needs.

    python packaging/make_icon.py build/icon.icns        # .icns for the .app
    python packaging/make_icon.py build/icon.png --png   # single 1024px PNG (Linux later)
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen  # noqa: E402

ICONSET_SIZES = (16, 32, 64, 128, 256, 512, 1024)


def render(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 1024.0  # design in a 1024 box

    # Tile: macOS-style rounded square with a subtle vertical gradient.
    tile = QRectF(64 * s, 64 * s, 896 * s, 896 * s)
    gradient = QLinearGradient(tile.topLeft(), tile.bottomLeft())
    gradient.setColorAt(0.0, QColor("#2f3440"))
    gradient.setColorAt(1.0, QColor("#15181f"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(gradient))
    painter.drawRoundedRect(tile, 200 * s, 200 * s)

    # Film-strip perforations down both edges.
    painter.setBrush(QColor("#0b0d11"))
    for i in range(6):
        y = tile.top() + (90 + i * 130) * s
        for x in (tile.left() + 70 * s, tile.right() - 130 * s):
            painter.drawRoundedRect(QRectF(x, y, 60 * s, 80 * s), 12 * s, 12 * s)

    # In/out cut marks bracketing the play mark.
    pen = QPen(QColor("#f5b942"), 44 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    left = QPainterPath(QPointF(330 * s, 330 * s))
    left.lineTo(280 * s, 330 * s)
    left.lineTo(280 * s, 694 * s)
    left.lineTo(330 * s, 694 * s)
    painter.drawPath(left)
    right = QPainterPath(QPointF(694 * s, 330 * s))
    right.lineTo(744 * s, 330 * s)
    right.lineTo(744 * s, 694 * s)
    right.lineTo(694 * s, 694 * s)
    painter.drawPath(right)

    # Play mark.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#e8ecf3"))
    play = QPainterPath(QPointF(430 * s, 360 * s))
    play.lineTo(650 * s, 512 * s)
    play.lineTo(430 * s, 664 * s)
    play.closeSubpath()
    painter.drawPath(play)

    painter.end()
    return image


def write_icns(target: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for size in ICONSET_SIZES:
            image = render(size)
            if size <= 512:
                image.save(str(iconset / f"icon_{size}x{size}.png"))
            if size >= 32:
                image.save(str(iconset / f"icon_{size // 2}x{size // 2}@2x.png"))
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(target)], check=True)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    target = Path(argv[1])
    _app = QGuiApplication.instance() or QGuiApplication([])
    if "--png" in argv or target.suffix == ".png":
        target.parent.mkdir(parents=True, exist_ok=True)
        render(1024).save(str(target))
    else:
        write_icns(target)
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
