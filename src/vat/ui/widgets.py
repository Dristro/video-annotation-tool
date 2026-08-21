from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLineEdit


class TransportLineEdit(QLineEdit):
    """A QLineEdit that forwards plain Left/Right/Up/Down to app-level
    transport/playlist-navigation actions instead of using them for
    in-field cursor movement.

    Reported as a real bug: once a score field had focus, the global
    Left/Right (seek) and Up/Down (prev/next video) shortcuts went dead,
    because QLineEdit's own key handling claims plain arrow keys for
    cursor movement before they ever reach shortcut dispatch -- no
    QShortcut context setting can override that, since the focused
    widget's own keyPressEvent handles them directly. Score fields are
    short numeric entries, so losing in-field arrow-key cursor movement is
    a deliberate, low-cost tradeoff for keeping transport controls live
    while one has focus.
    """

    ARROW_KEYS = {
        Qt.Key.Key_Left: "left",
        Qt.Key.Key_Right: "right",
        Qt.Key.Key_Up: "up",
        Qt.Key.Key_Down: "down",
    }

    arrow_key_pressed = Signal(str)  # "left" | "right" | "up" | "down"

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.modifiers() == Qt.KeyboardModifier.NoModifier and event.key() in self.ARROW_KEYS:
            self.arrow_key_pressed.emit(self.ARROW_KEYS[event.key()])
            event.accept()
            return
        super().keyPressEvent(event)
