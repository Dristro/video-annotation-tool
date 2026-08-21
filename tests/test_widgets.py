import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.ui.widgets import TransportLineEdit  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _press(edit: TransportLineEdit, key, text: str = "", modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    event = QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text)
    edit.keyPressEvent(event)


def test_plain_arrow_keys_are_forwarded_not_used_for_cursor_movement(qapp):
    edit = TransportLineEdit()
    edit.setText("50")
    edit.setCursorPosition(0)  # cursor at the very start

    seen = []
    edit.arrow_key_pressed.connect(seen.append)

    _press(edit, Qt.Key.Key_Right)

    assert seen == ["right"]
    # A normal QLineEdit would move the cursor to position 1 on Right;
    # since we intercepted it, the cursor must not have moved.
    assert edit.cursorPosition() == 0


def test_all_four_directions_forwarded(qapp):
    edit = TransportLineEdit()
    seen = []
    edit.arrow_key_pressed.connect(seen.append)

    for key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
        _press(edit, key)

    assert seen == ["left", "right", "up", "down"]


def test_regular_typing_still_works(qapp):
    edit = TransportLineEdit()
    _press(edit, Qt.Key.Key_5, text="5")
    _press(edit, Qt.Key.Key_0, text="0")
    assert edit.text() == "50"


def test_modified_arrow_keys_are_not_intercepted(qapp):
    # Only plain (unmodified) arrow keys are transport shortcuts -- e.g.
    # Shift+Left for text selection should still behave like a normal
    # QLineEdit, not fire a navigation event.
    edit = TransportLineEdit()
    edit.setText("50")
    edit.setCursorPosition(2)
    seen = []
    edit.arrow_key_pressed.connect(seen.append)

    _press(edit, Qt.Key.Key_Left, modifiers=Qt.KeyboardModifier.ShiftModifier)

    assert seen == []
