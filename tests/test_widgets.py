from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtCore import QCoreApplication
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.ui.widgets import SingleStrokeKeySequenceEdit, TransportLineEdit  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication | QCoreApplication:
    return QApplication.instance() or QApplication([])


def _press(edit: TransportLineEdit, key: Qt.Key, text: str = "", modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    event = QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text)
    edit.keyPressEvent(event)


def test_plain_arrow_keys_are_forwarded_not_used_for_cursor_movement(qapp) -> None:
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


def test_all_four_directions_forwarded(qapp) -> None:
    edit = TransportLineEdit()
    seen = []
    edit.arrow_key_pressed.connect(seen.append)

    for key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
        _press(edit, key)

    assert seen == ["left", "right", "up", "down"]


def test_regular_typing_still_works(qapp) -> None:
    edit = TransportLineEdit()
    _press(edit, Qt.Key.Key_5, text="5")
    _press(edit, Qt.Key.Key_0, text="0")
    assert edit.text() == "50"


def test_modified_arrow_keys_are_not_intercepted(qapp) -> None:
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


def test_single_stroke_key_sequence_edit_records_one_combo(qapp) -> None:
    edit = SingleStrokeKeySequenceEdit()
    edit.show()

    QTest.keyClick(edit, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)

    assert edit.keySequence().toString() == "Ctrl+G"


def test_single_stroke_key_sequence_edit_replaces_not_appends(qapp) -> None:
    # Regression test: plain QKeySequenceEdit accumulates up to 4 presses
    # into a multi-stroke chord by default -- pressing Ctrl+G, then
    # Ctrl+Shift+G to correct it, silently produced "Ctrl+G, Ctrl+Shift+G"
    # (a two-step chord) instead of replacing the recording. Reported as
    # a real bug ("multi-key shortcuts not working").
    edit = SingleStrokeKeySequenceEdit()
    edit.show()

    QTest.keyClick(edit, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(edit, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)

    assert edit.keySequence().toString() == "Ctrl+Shift+G"


def test_single_stroke_key_sequence_edit_multiple_corrections(qapp) -> None:
    edit = SingleStrokeKeySequenceEdit()
    edit.show()

    QTest.keyClick(edit, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(edit, Qt.Key.Key_B, Qt.KeyboardModifier.AltModifier)
    QTest.keyClick(edit, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)

    assert edit.keySequence().toString() == "Ctrl+Shift+C"
