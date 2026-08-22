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


def test_pending_justification_defaults_empty(panel):
    assert panel.pending_justification() == ""


def test_pending_justification_returns_stripped_text(panel):
    panel._justification_input.setText("  clear foul, hand ball  ")
    assert panel.pending_justification() == "clear foul, hand ball"


def test_clear_pending_clears_justification(panel):
    panel._justification_input.setText("some notes")
    panel.clear_pending()
    assert panel.pending_justification() == ""


def test_selecting_a_cut_prefills_justification(panel):
    cut = Cut(start=1.0, end=2.0, label="goal", justification="clean strike, top corner")
    panel.set_cuts([cut], [], False)

    panel.select_cut_by_id(cut.id)

    assert panel.pending_justification() == "clean strike, top corner"


def test_selecting_a_cut_without_justification_blanks_field(panel):
    panel._justification_input.setText("stale text from a previous selection")
    cut = Cut(start=1.0, end=2.0, label="goal")
    panel.set_cuts([cut], [], False)

    panel.select_cut_by_id(cut.id)

    assert panel.pending_justification() == ""


def test_start_here_prefills_justification_from_front_half(panel):
    cut = Cut(
        start=280.0, end=300.0, label="goal", justification="ends here",
        continuation_id="link1", continues_forward=True,
    )
    panel.set_pending_continuation(cut)

    panel._on_start_continuation()

    assert panel.pending_justification() == "ends here"


def test_set_cuts_shows_truncated_justification_in_list(panel):
    cut = Cut(start=1.0, end=2.0, label="goal", justification="clean strike, top corner")
    panel.set_cuts([cut], [], False)

    assert "clean strike, top corner" in panel._cuts_list.item(0).text()


def test_set_cuts_truncates_long_justification(panel):
    long_text = "x" * 100
    cut = Cut(start=1.0, end=2.0, label="goal", justification=long_text)
    panel.set_cuts([cut], [], False)

    text = panel._cuts_list.item(0).text()
    assert "x" * 40 in text
    assert "x" * 41 not in text
    assert "…" in text


def test_set_cuts_omits_justification_marker_when_absent(panel):
    cut = Cut(start=1.0, end=2.0, label="goal")
    panel.set_cuts([cut], [], False)

    assert '"' not in panel._cuts_list.item(0).text()


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


def test_set_pending_continuations_single_hides_next_button(panel):
    cut = Cut(start=280.0, end=300.0, label="goal", continuation_id="link1", continues_forward=True)
    panel.set_pending_continuations([cut])

    assert panel._next_continuation_btn.isHidden() is True
    assert "goal" in panel._continuation_banner_label.text()
    assert "(" not in panel._continuation_banner_label.text()  # no "(1/2)"-style count for a single one


def test_set_pending_continuations_multiple_shows_next_button_and_count(panel):
    a = Cut(start=100.0, end=110.0, label="goal", continuation_id="link1", continues_forward=True)
    b = Cut(start=200.0, end=210.0, label="foul", continuation_id="link2", continues_forward=True)
    panel.set_pending_continuations([a, b])

    assert panel._next_continuation_btn.isHidden() is False
    assert "goal" in panel._continuation_banner_label.text()
    assert "(1/2)" in panel._continuation_banner_label.text()


def test_next_continuation_cycles_and_wraps(panel):
    a = Cut(start=100.0, end=110.0, label="goal", continuation_id="link1", continues_forward=True)
    b = Cut(start=200.0, end=210.0, label="foul", continuation_id="link2", continues_forward=True)
    panel.set_pending_continuations([a, b])

    panel._on_next_continuation()
    assert "foul" in panel._continuation_banner_label.text()
    assert "(2/2)" in panel._continuation_banner_label.text()

    panel._on_next_continuation()  # wraps back to the first
    assert "goal" in panel._continuation_banner_label.text()
    assert "(1/2)" in panel._continuation_banner_label.text()


def test_start_here_acts_on_whichever_continuation_is_currently_shown(panel):
    a = Cut(start=100.0, end=110.0, label="goal", continuation_id="link1", continues_forward=True)
    b = Cut(start=200.0, end=210.0, label="foul", continuation_id="link2", continues_forward=True)
    panel.set_labels([Label(name="goal", shortcut="g"), Label(name="foul", shortcut="f")])
    panel.set_pending_continuations([a, b])
    panel._on_next_continuation()

    panel._on_start_continuation()

    assert panel.selected_label_name() == "foul"
    assert panel.completing_continuation_id() == "link2"


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


def test_edit_enabled_when_mark_in_out_untouched(panel):
    cut = Cut(start=1.0, end=2.0, label="goal")
    panel.set_cuts([cut], [], False)
    panel.select_cut_by_id(cut.id)

    assert panel._edit_cut_btn.isEnabled() is True
    assert panel.pending_retime() is None


def test_edit_disabled_when_only_mark_in_set(panel):
    cut = Cut(start=1.0, end=2.0, label="goal")
    panel.set_cuts([cut], [], False)
    panel.select_cut_by_id(cut.id)

    panel.set_pending_in(5.0)

    assert panel._edit_cut_btn.isEnabled() is False


def test_edit_enabled_with_valid_retime_range(panel):
    cut = Cut(start=1.0, end=2.0, label="goal")
    panel.set_cuts([cut], [], False)
    panel.select_cut_by_id(cut.id)

    panel.set_pending_in(5.0)
    panel.set_pending_out(10.0)

    assert panel._edit_cut_btn.isEnabled() is True
    assert panel.pending_retime() == (5.0, 10.0)


def test_edit_disabled_when_retime_out_before_in(panel):
    cut = Cut(start=1.0, end=2.0, label="goal")
    panel.set_cuts([cut], [], False)
    panel.select_cut_by_id(cut.id)

    panel.set_pending_in(10.0)
    panel.set_pending_out(5.0)

    assert panel._edit_cut_btn.isEnabled() is False


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


def test_break_continuation_button_visible_only_for_linked_cuts(panel):
    # isVisible() is always False in these headless tests regardless of
    # setVisible() (the top-level window is never shown) -- isHidden()
    # reflects the explicit setVisible() call on this widget itself,
    # independent of ancestor visibility (see CLAUDE.md's testing notes).
    linked = Cut(start=1.0, end=2.0, label="goal", continuation_id="link1", continues_forward=True)
    ordinary = Cut(start=5.0, end=6.0, label="goal")
    panel.set_cuts([linked, ordinary], [], False)

    panel.select_cut_by_id(linked.id)
    assert panel._break_continuation_btn.isHidden() is False

    panel.select_cut_by_id(ordinary.id)
    assert panel._break_continuation_btn.isHidden() is True


def test_break_continuation_emits_selected_cut_id(panel):
    linked = Cut(start=1.0, end=2.0, label="goal", continuation_id="link1", continues_forward=True)
    panel.set_cuts([linked], [], False)
    panel.select_cut_by_id(linked.id)

    emitted = []
    panel.break_continuation_requested.connect(emitted.append)
    panel._emit_break_continuation()

    assert emitted == [linked.id]


def test_set_cuts_shows_continuation_markers(panel):
    front_half = Cut(start=280.0, end=300.0, label="goal", continuation_id="link1", continues_forward=True)
    back_half = Cut(start=0.0, end=60.0, label="goal", continuation_id="link1", continues_forward=False)
    ordinary = Cut(start=100.0, end=110.0, label="goal")

    panel.set_cuts([front_half, back_half, ordinary], [], False)

    assert "→" in panel._cuts_list.item(0).text()
    assert "#link" in panel._cuts_list.item(0).text()
    assert "←" in panel._cuts_list.item(1).text()
    assert "#link" in panel._cuts_list.item(1).text()
    assert "→" not in panel._cuts_list.item(2).text() and "←" not in panel._cuts_list.item(2).text()
