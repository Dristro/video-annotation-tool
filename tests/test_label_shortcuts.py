import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QKeySequence, QShortcut  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit, QMainWindow  # noqa: E402

from vat.models.label import Label  # noqa: E402
from vat.ui.label_shortcuts import LabelShortcutManager  # noqa: E402

# The real label set this tool is used with -- three prefix collisions
# ("S" vs "S, L"/"S, R", "J" vs "J, R") plus a two-stroke sequence whose
# first stroke is not itself a binding ("R, E").
REAL_LABELS = [
    Label("Speeding", "S"),
    Label("Jump Red Light", "J, R"),
    Label("Road Entry", "R, E"),
    Label("Switch Lane", "S, L"),
    Label("U Turn", "U"),
    Label("Stopping on road", "S, R"),
    Label("Dangerous Turn", "D"),
    Label("J-Walking", "J"),
    Label("Late braking", "B"),
]

TIMEOUT_MS = 60  # keep the chord window short so tests don't crawl


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def harness(qapp):
    window = QMainWindow()
    line_edit = QLineEdit()
    window.setCentralWidget(line_edit)
    window.show()
    window.activateWindow()
    QTest.qWaitForWindowExposed(window)

    fired = []
    manager = LabelShortcutManager(window, chord_timeout_ms=TIMEOUT_MS)
    manager.label_activated.connect(fired.append)
    yield window, line_edit, manager, fired
    window.close()


def _settle(qapp, ms=TIMEOUT_MS * 3):
    deadline = time.monotonic() + ms / 1000
    while time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)


def _press(qapp, target, *keys):
    for key in keys:
        QTest.keyClick(target, key)
        qapp.processEvents()
    _settle(qapp)


@pytest.mark.parametrize(
    "keys, expected",
    [
        ((Qt.Key.Key_S,), ["Speeding"]),
        ((Qt.Key.Key_S, Qt.Key.Key_L), ["Switch Lane"]),
        ((Qt.Key.Key_S, Qt.Key.Key_R), ["Stopping on road"]),
        ((Qt.Key.Key_J,), ["J-Walking"]),
        ((Qt.Key.Key_J, Qt.Key.Key_R), ["Jump Red Light"]),
        ((Qt.Key.Key_R, Qt.Key.Key_E), ["Road Entry"]),
        ((Qt.Key.Key_U,), ["U Turn"]),
        ((Qt.Key.Key_D,), ["Dangerous Turn"]),
    ],
)
def test_every_real_label_shortcut_reaches_its_own_label(qapp, harness, keys, expected):
    # Regression test for the core bug: Qt's shortcut map prefers an exact
    # match over a partial one, so registering "S" and "S, L" as ordinary
    # QShortcuts made pressing S fire "Speeding" immediately and left
    # "Switch Lane" permanently unreachable. Reported as "if a shortcut (S)
    # and (S+L) exist, pressing S+L only selects the label with S".
    window, _, manager, fired = harness
    manager.set_labels(REAL_LABELS)

    _press(qapp, window, *keys)

    assert fired == expected


def test_prefix_shortcut_is_not_registered_twice_with_qt(qapp, harness):
    # The longer sequences must NOT be handed to Qt at all -- that is what
    # keeps its exact-match-wins rule from shadowing them again.
    window, _, manager, _ = harness
    manager.set_labels(REAL_LABELS)

    registered = sorted(s.key().toString() for s in manager._shortcuts)

    assert registered == ["B", "D", "J", "R, E", "S", "U"]
    assert manager.shortcut_texts() == ["B", "D", "J", "J, R", "R, E", "S", "S, L", "S, R", "U"]


def test_prefix_shortcut_followed_by_unrelated_key_fires_both(qapp, harness):
    # Pressing S then some other bound key must commit "S" and then let the
    # other key do its normal thing -- neither may be swallowed.
    window, _, manager, fired = harness
    manager.set_labels(REAL_LABELS)

    _press(qapp, window, Qt.Key.Key_S, Qt.Key.Key_U)

    assert fired == ["Speeding", "U Turn"]


def test_escape_cancels_a_pending_sequence(qapp, harness):
    window, _, manager, fired = harness
    manager.set_labels(REAL_LABELS)

    _press(qapp, window, Qt.Key.Key_S, Qt.Key.Key_Escape)

    assert fired == []


def test_typing_in_a_text_field_never_selects_a_label(qapp, harness):
    # QLineEdit claims plain printable keys via ShortcutOverride, so the
    # bare "S" shortcut never fires while it has focus -- which also means
    # no pending sequence opens and no key gets intercepted.
    window, line_edit, manager, fired = harness
    manager.set_labels(REAL_LABELS)
    line_edit.setFocus()

    _press(qapp, line_edit, Qt.Key.Key_S, Qt.Key.Key_L)

    assert line_edit.text() == "sl"
    assert fired == []


def test_chord_completion_does_not_leak_into_the_focused_widget(qapp, harness):
    # The completing stroke is consumed: finishing "S, L" must not also type
    # an "l" somewhere.
    window, line_edit, manager, fired = harness
    manager.set_labels(REAL_LABELS)

    _press(qapp, window, Qt.Key.Key_S, Qt.Key.Key_L)

    assert fired == ["Switch Lane"]
    assert line_edit.text() == ""


def test_labels_without_shortcuts_are_skipped(qapp, harness):
    window, _, manager, _ = harness
    manager.set_labels([Label("No Key", ""), Label("Keyed", "K")])

    assert manager.shortcut_texts() == ["K"]


def test_set_labels_replaces_previous_bindings(qapp, harness):
    window, _, manager, fired = harness
    manager.set_labels([Label("Old", "O")])
    manager.set_labels([Label("New", "N")])

    _press(qapp, window, Qt.Key.Key_O)
    assert fired == []

    _press(qapp, window, Qt.Key.Key_N)
    assert fired == ["New"]


def test_three_stroke_chain_resolves_each_length(qapp, harness):
    # Nothing in the app builds these today, but the pending window is
    # written to nest rather than assume exactly two strokes.
    window, _, manager, fired = harness
    manager.set_labels([Label("One", "A"), Label("Two", "A, B"), Label("Three", "A, B, C")])

    _press(qapp, window, Qt.Key.Key_A)
    assert fired == ["One"]

    fired.clear()
    _press(qapp, window, Qt.Key.Key_A, Qt.Key.Key_B)
    assert fired == ["Two"]

    fired.clear()
    _press(qapp, window, Qt.Key.Key_A, Qt.Key.Key_B, Qt.Key.Key_C)
    assert fired == ["Three"]


def test_pending_sequence_does_not_block_unrelated_app_shortcuts(qapp, harness):
    # A non-label QShortcut (Space = play/pause, in the real app) pressed
    # during the pending window must still fire.
    window, _, manager, fired = harness
    manager.set_labels(REAL_LABELS)
    space_presses = []
    space = QShortcut(QKeySequence(Qt.Key.Key_Space), window)
    space.activated.connect(lambda: space_presses.append(1))

    _press(qapp, window, Qt.Key.Key_S, Qt.Key.Key_Space)

    assert fired == ["Speeding"]
    assert space_presses == [1]
