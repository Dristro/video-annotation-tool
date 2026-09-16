from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QWidget

from vat.models.label import Label

# How long a shortcut that is also the *start* of a longer one waits for the
# rest of that longer one before committing to itself. Only ever applies to
# such prefix shortcuts -- every other label shortcut still fires instantly.
CHORD_TIMEOUT_MS = 500

# Plain ints rather than Qt.Key members: QKeyEvent.key() can report a code
# with no enum member (unusual/media keys), and Qt.Key(that) raises.
_MODIFIER_KEYS = {
    int(key)
    for key in (
        Qt.Key.Key_Shift,
        Qt.Key.Key_Control,
        Qt.Key.Key_Meta,
        Qt.Key.Key_Alt,
        Qt.Key.Key_AltGr,
        Qt.Key.Key_CapsLock,
        Qt.Key.Key_NumLock,
        Qt.Key.Key_ScrollLock,
    )
}


def _is_prefix_of(shorter: str, longer: str) -> bool:
    """Whether `longer` starts with `shorter` plus at least one more stroke.

    QKeySequence.toString() joins strokes with ", " (e.g. "S, L",
    "Ctrl+G, Shift+A") and no single stroke contains a comma followed by a
    space, so comparing the canonical strings is unambiguous.
    """
    return shorter != longer and longer.startswith(shorter + ", ")


class LabelShortcutManager(QObject):
    """Dispatches the project's label shortcuts, including ones where a
    short shortcut is the beginning of a longer one.

    Why this exists instead of a plain `QShortcut` per label: **Qt's
    shortcut map always prefers an exact match over a partial one**, so
    registering both "S" and "S, L" as ordinary QShortcuts makes "S, L"
    permanently unreachable -- pressing S fires "S" immediately and the
    chord never gets the chance to complete. Verified directly against
    Qt 6.11, and reported as a real bug against the real project this tool
    was written for, which has exactly that collision three times over
    ("S"/"S, L"/"S, R" and "J"/"J, R").

    How it works:

    - A binding that no other binding starts with is registered as an
      ordinary `QShortcut` and fires immediately -- unchanged behavior,
      including plain multi-stroke chords like "R, E" whose first stroke
      isn't itself a binding (Qt handles those natively just fine).
    - A binding that *is* the start of a longer one ("S") is registered as
      a `QShortcut` too, but activating it only opens a pending window:
      the manager grabs the next key press, and if it completes a longer
      binding ("S, L") that label wins. Otherwise -- an unrelated key, Esc,
      or `CHORD_TIMEOUT_MS` elapsing -- the short binding commits.
    - The longer bindings are deliberately *not* registered with Qt at all;
      they exist only as chord completions, which is what keeps Qt's
      exact-match-wins rule from re-breaking them.

    Relying on the short binding's own `QShortcut` to open the pending
    window (rather than filtering every key press application-wide) is
    what preserves the important property that typing in a text field
    never triggers a label: `QLineEdit` claims plain printable keys via
    `ShortcutOverride`, so the "S" shortcut doesn't fire while one has
    focus -- and therefore no pending window opens and no key gets
    intercepted either.

    The pending window intercepts `ShortcutOverride`, **not** `KeyPress`.
    That matters, and cost a debugging round to find: Qt consults its
    shortcut map *before* the key is delivered as a `KeyPress`, so a
    KeyPress-based filter never sees a key the shortcut map already
    claimed. With the real label set that broke two cases -- "S, R" lost
    its R to the (registered, unrelated) "R, E" chord's partial match, and
    "S" followed by some other bound key lost the pending "S" entirely.
    `ShortcutOverride` is dispatched through ordinary event filters first,
    and accepting it makes Qt skip shortcut handling for that key, which
    is exactly the hook needed.
    """

    label_activated = Signal(str)  # label name

    def __init__(self, window: QWidget, chord_timeout_ms: int = CHORD_TIMEOUT_MS) -> None:
        super().__init__(window)
        self._window = window
        self._shortcuts: list[QShortcut] = []
        self._bindings: dict[str, str] = {}  # canonical sequence text -> label name
        self._prefixes: set[str] = set()  # bindings that start a longer binding
        self._pending: str | None = None
        self._filtering = False
        # Key whose ShortcutOverride was consumed as a chord completion, so
        # the KeyPress that follows it can be dropped too rather than
        # landing in whatever widget has focus.
        self._swallow_key: int | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(chord_timeout_ms)
        self._timer.timeout.connect(self._commit_pending)

    # -- Registration ------------------------------------------------------------
    def set_labels(self, labels: list[Label]) -> None:
        """(Re)bind every label's shortcut. Called on startup and after any
        label edit/rename/project switch, since the set of valid shortcuts
        can change at any time (REQUIREMENT.md: label shortcuts are
        editable after project creation).
        """
        self._cancel_pending()
        for shortcut in self._shortcuts:
            shortcut.setParent(None)
        self._shortcuts.clear()

        self._bindings = {}
        for label in labels:
            if not label.shortcut:
                continue
            sequence = QKeySequence(label.shortcut)
            if sequence.count() == 0:
                continue
            # First label wins on a duplicate, matching the old behavior's
            # "only one of them can ever fire" (the label editor warns).
            self._bindings.setdefault(sequence.toString(), label.name)

        self._prefixes = {
            text for text in self._bindings if any(_is_prefix_of(text, other) for other in self._bindings)
        }
        for text in self._bindings:
            if self._completes_a_binding(text):
                continue  # reachable only as a chord completion, see class docstring
            shortcut = QShortcut(QKeySequence(text), self._window)
            shortcut.activated.connect(lambda t=text: self._advance(t))
            self._shortcuts.append(shortcut)

    def _completes_a_binding(self, text: str) -> bool:
        return any(_is_prefix_of(other, text) for other in self._bindings)

    def shortcut_texts(self) -> list[str]:
        """Every bound sequence, whether it's a real QShortcut or only
        reachable as a chord completion. For tests/diagnostics.
        """
        return sorted(self._bindings)

    # -- Dispatch ------------------------------------------------------------
    def _advance(self, text: str) -> None:
        """Act on a fully-matched sequence: either fire its label, or -- if
        a longer binding starts with it -- wait to see whether the user is
        partway through that longer one.
        """
        self._cancel_pending()
        if text in self._prefixes:
            self._pending = text
            self._start_filtering()
            self._timer.start()
            return
        name = self._bindings.get(text)
        if name is not None:
            self.label_activated.emit(name)

    def _commit_pending(self) -> None:
        text = self._pending
        self._cancel_pending()
        if text is None:
            return
        name = self._bindings.get(text)
        if name is not None:
            self.label_activated.emit(name)

    def _cancel_pending(self) -> None:
        self._pending = None
        self._timer.stop()
        self._stop_filtering()

    def _start_filtering(self) -> None:
        app = QApplication.instance()
        if app is not None and not self._filtering:
            app.installEventFilter(self)
            self._filtering = True

    def _stop_filtering(self) -> None:
        if self._pending is not None or self._swallow_key is not None:
            return  # still work left for the filter to do
        app = QApplication.instance()
        if app is not None and self._filtering:
            app.removeEventFilter(self)
        self._filtering = False

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt override)
        event_type = event.type()
        if event_type == QEvent.Type.KeyPress and self._swallow_key is not None:
            swallowed, self._swallow_key = self._swallow_key, None
            self._stop_filtering()
            return event.key() == swallowed
        if event_type != QEvent.Type.ShortcutOverride or self._pending is None:
            return False
        key = event.key()
        if key in _MODIFIER_KEYS or event.isAutoRepeat():
            # Holding Shift to reach the second stroke must neither complete
            # nor cancel the sequence.
            return False
        if key == int(Qt.Key.Key_Escape):
            self._cancel_pending()
            return False
        candidate = f"{self._pending}, {QKeySequence(event.keyCombination()).toString()}"
        if candidate in self._bindings:
            self._pending = None  # _advance() would otherwise cancel-then-restart
            self._timer.stop()
            self._swallow_key = event.key()
            self._advance(candidate)
            # Accepting a ShortcutOverride is what tells Qt to skip its own
            # shortcut handling for this key -- without it, a key that also
            # starts some other registered sequence (R, in "R, E") gets
            # claimed by the shortcut map instead of completing this one.
            event.accept()
            return True
        # Not a continuation -- commit the shorter binding and let the key
        # carry on to whatever it normally does, shortcut handling included.
        self._commit_pending()
        return False
