import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from vat.models.cut import Cut  # noqa: E402
from vat.models.label import Label  # noqa: E402
from vat.models.score_definition import ScoreDefinition  # noqa: E402
from vat.ui.inspector_panel import InspectorPanel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(qapp):
    p = InspectorPanel()
    p.set_labels([Label(name="goal", shortcut="g")])
    return p


def test_continues_checkbox_relaxes_mark_out_requirement(panel):
    panel.set_pending_in(10.0)
    assert panel._add_cut_btn.isEnabled() is False  # no Mark Out yet

    panel._continues_checkbox.setChecked(True)
    assert panel._add_cut_btn.isEnabled() is True  # Mark Out no longer required

    panel._continues_checkbox.setChecked(False)
    assert panel._add_cut_btn.isEnabled() is False  # back to requiring both


def test_continues_checkbox_still_requires_mark_in(panel):
    panel._continues_checkbox.setChecked(True)
    assert panel._add_cut_btn.isEnabled() is False  # no Mark In at all


def test_set_continuation_allowed_false_disables_and_unchecks(panel):
    panel._continues_checkbox.setChecked(True)
    panel.set_continuation_allowed(False)
    assert panel._continues_checkbox.isEnabled() is False
    assert panel._continues_checkbox.isChecked() is False


def test_pending_continuation_banner_shows_and_hides(panel):
    cut = Cut(start=280.0, end=300.0, label="goal", continuation_id="link1", continues_forward=True)

    panel.set_pending_continuation(cut)
    assert "goal" in panel._continuation_banner_label.text()

    panel.set_pending_continuation(None)
    assert panel._continuation_banner_label.text() == "" or panel._pending_continuation_cut is None


def test_start_here_prefills_label_scores_and_mark_in(panel):
    panel.set_score_definitions(True, [ScoreDefinition(name="Technique", minimum=0, maximum=100)])
    panel.set_labels([Label(name="goal", shortcut="g")])
    cut = Cut(
        start=280.0, end=300.0, label="goal", scores={"Technique": 87.5},
        continuation_id="link1", continues_forward=True,
    )
    panel.set_pending_continuation(cut)

    panel._on_start_continuation()

    assert panel.selected_label_name() == "goal"
    assert panel._score_inputs["Technique"].text() == "87.5"
    assert panel.pending_in() == 0.0
    assert panel.pending_out() is None
    assert panel.completing_continuation_id() == "link1"


def test_selecting_an_existing_cut_clears_continuation_completion_state(panel):
    front_half = Cut(start=280.0, end=300.0, label="goal", continuation_id="link1", continues_forward=True)
    panel.set_pending_continuation(front_half)
    panel._on_start_continuation()
    assert panel.completing_continuation_id() == "link1"

    other_cut = Cut(start=1.0, end=2.0, label="goal")
    panel.set_cuts([other_cut], [], False)
    panel.select_cut_by_id(other_cut.id)

    assert panel.completing_continuation_id() is None
    assert panel._continues_checkbox.isChecked() is False


def test_delete_cut_asks_for_confirmation_and_emits_when_confirmed(panel, monkeypatch):
    cut = Cut(start=1.0, end=2.0, label="goal")
    panel.set_cuts([cut], [], False)
    panel.select_cut_by_id(cut.id)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    emitted = []
    panel.delete_cut_requested.connect(emitted.append)

    panel._emit_delete_cut()

    assert emitted == [cut.id]


def test_delete_cut_does_not_emit_when_confirmation_declined(panel, monkeypatch):
    cut = Cut(start=1.0, end=2.0, label="goal")
    panel.set_cuts([cut], [], False)
    panel.select_cut_by_id(cut.id)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    emitted = []
    panel.delete_cut_requested.connect(emitted.append)

    panel._emit_delete_cut()

    assert emitted == []


def test_set_cuts_shows_continuation_markers(panel):
    front_half = Cut(start=280.0, end=300.0, label="goal", continuation_id="link1", continues_forward=True)
    back_half = Cut(start=0.0, end=60.0, label="goal", continuation_id="link1", continues_forward=False)
    ordinary = Cut(start=100.0, end=110.0, label="goal")

    panel.set_cuts([front_half, back_half, ordinary], [], False)

    assert "→" in panel._cuts_list.item(0).text()
    assert "←" in panel._cuts_list.item(1).text()
    assert "→" not in panel._cuts_list.item(2).text() and "←" not in panel._cuts_list.item(2).text()
