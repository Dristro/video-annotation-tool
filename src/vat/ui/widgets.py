from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QKeySequenceEdit, QLineEdit


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


class SingleStrokeKeySequenceEdit(QKeySequenceEdit):
    """A QKeySequenceEdit that only ever records the single most recent key
    combination, rather than Qt's default behavior of accumulating up to 4
    presses into a multi-stroke *chord* (e.g. "Ctrl+K, Ctrl+G", the
    VSCode-style two-step shortcut).

    Reported as a real bug: "multi-key shortcuts not working". Root cause,
    reproduced directly: pressing Ctrl+G then, to correct it, pressing
    Ctrl+Shift+G does *not* replace the recorded value -- it appends,
    silently producing "Ctrl+G, Ctrl+Shift+G". That's a shortcut requiring
    both combos pressed in sequence, with zero visual indication anything
    but a plain single combo was recorded, so a single press of either
    combo alone appeared to just do nothing. Label shortcuts (the only use
    of QKeySequenceEdit in this app) are plain "press this combo" bindings,
    never chords, so each fresh key press clears the field first --
    always replacing, never extending.
    """

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.clear()
        super().keyPressEvent(event)
