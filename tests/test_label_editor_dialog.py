from vat.project.project import Project
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from vat.project.project import Project  # noqa: E402
from vat.ui.label_editor_dialog import LabelEditorDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication | QCoreApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def project(qapp, tmp_project_dir, tmp_videos_dir) -> Project:
    p = Project.create(tmp_project_dir, tmp_videos_dir)
    p.add_label("goal", shortcut="Ctrl+G")
    return p


def test_warn_if_shortcut_collides_flags_other_label_with_same_shortcut(project, monkeypatch) -> None:
    dialog = LabelEditorDialog(project)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok
    )

    dialog.content._warn_if_shortcut_collides("Ctrl+G", excluding_name="foul")

    assert len(warnings) == 1


def test_warn_if_shortcut_collides_silent_when_unique(project, monkeypatch) -> None:
    dialog = LabelEditorDialog(project)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok
    )

    dialog.content._warn_if_shortcut_collides("Ctrl+F", excluding_name="foul")

    assert warnings == []


def test_warn_if_shortcut_collides_excludes_own_label(project, monkeypatch) -> None:
    # Editing "goal" itself and keeping its own shortcut must not warn against itself.
    dialog = LabelEditorDialog(project)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok
    )

    dialog.content._warn_if_shortcut_collides("Ctrl+G", excluding_name="goal")

    assert warnings == []


def test_split_and_join_strokes_round_trip() -> None:
    from vat.ui.label_editor_dialog import join_strokes, split_strokes

    assert split_strokes("") == ("", "")
    assert split_strokes("S") == ("S", "")
    assert split_strokes("S, L") == ("S", "L")
    assert split_strokes("Ctrl+G, Shift+A") == ("Ctrl+G", "Shift+A")
    assert split_strokes("A, B, C") == ("A", "B")  # form only offers two

    assert join_strokes("S", "") == "S"
    assert join_strokes("S", "L") == "S, L"
    assert join_strokes("", "L") == ""  # a second stroke alone is meaningless


def test_describe_shortcut_spells_out_a_two_key_sequence() -> None:
    from vat.ui.label_editor_dialog import describe_shortcut

    assert "No shortcut" in describe_shortcut("")
    assert describe_shortcut("S") == "Single key: press S."
    described = describe_shortcut("S, L")
    assert "press S, then L" in described
    assert "not together" in described


def test_label_form_splits_an_existing_two_key_shortcut_across_both_fields(qapp) -> None:
    from vat.ui.label_editor_dialog import _LabelFormDialog

    form = _LabelFormDialog(name="Switch Lane", shortcut="S, L")

    assert form._shortcut_edit.keySequence().toString() == "S"
    assert form._second_stroke_edit.keySequence().toString() == "L"
    assert form.values() == ("Switch Lane", "", "S, L")


def test_label_form_clear_shortcut_clears_both_fields(qapp) -> None:
    from vat.ui.label_editor_dialog import _LabelFormDialog

    form = _LabelFormDialog(name="Switch Lane", shortcut="S, L")
    form._clear_shortcut()

    assert form.values()[2] == ""


def test_warn_if_shortcut_collides_notes_a_shortcut_that_starts_another(project, monkeypatch) -> None:
    # "S" and "S, L" both work, but "S" alone has to wait out the chord
    # window first -- say so rather than let it be noticed as sluggishness.
    project.add_label("switch lane", shortcut="S, L")
    dialog = LabelEditorDialog(project)
    notes = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a, **k: notes.append(a) or QMessageBox.StandardButton.Ok
    )

    dialog.content._warn_if_shortcut_collides("S", excluding_name="speeding")

    assert len(notes) == 1
    assert "S, L" in notes[0][2]
