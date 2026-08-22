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

    Reported as a real bug: pressing Ctrl+G then, to correct it, pressing
    Ctrl+Shift+G does *not* replace the recorded value -- it appends,
    silently producing "Ctrl+G, Ctrl+Shift+G". That's a shortcut requiring
    both combos pressed in sequence, with zero visual indication anything
    but a plain single combo was recorded, so a single press of either
    combo alone appeared to just do nothing. Each fresh key press therefore
    clears the field first -- always replacing, never extending.

    Two-key label shortcuts ("S, L") are a real, supported thing, but they
    are *not* recorded by accumulating into one of these. `_LabelFormDialog`
    uses two of these fields side by side ("Shortcut" and "Then"), so the
    second stroke is always something the user opted into explicitly and
    correcting either one can never silently turn into a longer sequence.
    """

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.clear()
        super().keyPressEvent(event)
