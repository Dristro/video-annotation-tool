"""Undo/redo for label & score edits made through the settings widgets.

The widgets push pure-Project commands onto whatever UndoStack they're
given; nothing here needs MainWindow. Form dialogs are stubbed at the
class level (exec -> Accepted, values -> canned tuple) the same way the
widgets call them.
"""

from PySide6.QtCore import QCoreApplication
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from vat.project.project import Project  # noqa: E402
from vat.project.undo_stack import UndoStack  # noqa: E402
from vat.ui import label_editor_dialog, score_editor_dialog  # noqa: E402
from vat.ui.label_editor_dialog import _LabelsWidget  # noqa: E402
from vat.ui.score_editor_dialog import _ScoresWidget  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication | QCoreApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def project(qapp, tmp_project_dir, tmp_videos_dir) -> Project:
    p = Project.create(tmp_project_dir, tmp_videos_dir)
    p.add_label("goal", "G", "a goal")
    p.add_label("foul", "F")
    p.add_label("save", "S")
    p.add_score_definition("Technique", 0, 100, "float", "how clean")
    p.add_score_definition("Power", 0, 10, "int")
    p.add_cut("a.mp4", 1.0, 2.0, "foul", {"Technique": 50.0, "Power": 3})
    p.add_cut("b.mp4", 3.0, 4.0, "goal", {"Technique": 80.0})
    return p


def _accept_label_form(monkeypatch, values) -> None:
    monkeypatch.setattr(label_editor_dialog._LabelFormDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(label_editor_dialog._LabelFormDialog, "values", lambda self: values)


def _accept_score_form(monkeypatch, values) -> None:
    monkeypatch.setattr(score_editor_dialog._ScoreFormDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(score_editor_dialog._ScoreFormDialog, "values", lambda self: values)


def _select_row(widget, row: int) -> None:
    widget._table.selectRow(row)


# -- Labels ---------------------------------------------------------------

def test_rename_label_undo_reverts_config_and_every_cut(project, monkeypatch) -> None:
    stack = UndoStack()
    widget = _LabelsWidget(project, undo_stack=stack)
    _select_row(widget, 1)  # foul
    _accept_label_form(monkeypatch, ("infraction", "new desc", "X"))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    widget._on_edit()
    assert project.config.label_names() == ["goal", "infraction", "save"]
    assert project.get_entry("a.mp4").cuts[0].label == "infraction"

    stack.undo()
    assert project.config.label_names() == ["goal", "foul", "save"]
    restored = project.config.find_label("foul")
    assert (restored.shortcut, restored.description) == ("F", "")
    assert project.get_entry("a.mp4").cuts[0].label == "foul"
    assert project.get_entry("b.mp4").cuts[0].label == "goal"  # untouched throughout

    stack.redo()
    assert project.config.find_label("infraction").shortcut == "X"
    assert project.get_entry("a.mp4").cuts[0].label == "infraction"


def test_remove_labels_undo_restores_original_order(project, monkeypatch) -> None:
    stack = UndoStack()
    widget = _LabelsWidget(project, undo_stack=stack)
    widget._table.setSelectionMode(widget._table.SelectionMode.MultiSelection)
    _select_row(widget, 0)  # goal
    _select_row(widget, 1)  # foul
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    widget._on_remove()
    assert project.config.label_names() == ["save"]

    stack.undo()
    assert project.config.label_names() == ["goal", "foul", "save"]
    assert project.config.find_label("goal").description == "a goal"

    stack.redo()
    assert project.config.label_names() == ["save"]


def test_add_label_undo_removes_it_and_redo_reinserts_at_same_index(project, monkeypatch) -> None:
    stack = UndoStack()
    widget = _LabelsWidget(project, undo_stack=stack)
    _accept_label_form(monkeypatch, ("corner", "", "C"))

    widget._on_add()
    assert project.config.label_names()[-1] == "corner"

    stack.undo()
    assert "corner" not in project.config.label_names()
    stack.redo()
    assert project.config.label_names() == ["goal", "foul", "save", "corner"]


def test_no_stack_means_no_undo_but_edits_still_apply(project, monkeypatch) -> None:
    widget = _LabelsWidget(project)  # standalone use: no stack given
    _accept_label_form(monkeypatch, ("corner", "", ""))
    widget._on_add()
    assert "corner" in project.config.label_names()


# -- Scores ---------------------------------------------------------------

def test_rename_score_undo_reverts_definition_and_cut_keys(project, monkeypatch) -> None:
    stack = UndoStack()
    widget = _ScoresWidget(project, undo_stack=stack)
    _select_row(widget, 0)  # Technique
    _accept_score_form(monkeypatch, ("Form", "d", 0.0, 50.0, "int"))

    widget._on_edit()
    assert project.config.score_definition_names() == ["Form", "Power"]
    assert project.get_entry("a.mp4").cuts[0].scores == {"Form": 50.0, "Power": 3}

    stack.undo()
    restored = project.config.find_score_definition("Technique")
    assert (restored.minimum, restored.maximum, restored.dtype, restored.description) == (0.0, 100.0, "float", "how clean")
    assert project.get_entry("a.mp4").cuts[0].scores == {"Technique": 50.0, "Power": 3}
    assert project.get_entry("b.mp4").cuts[0].scores == {"Technique": 80.0}

    stack.redo()
    assert project.config.find_score_definition("Form").maximum == 50.0
    assert "Form" in project.get_entry("b.mp4").cuts[0].scores


def test_remove_and_add_score_definitions_are_undoable(project, monkeypatch) -> None:
    stack = UndoStack()
    widget = _ScoresWidget(project, undo_stack=stack)
    _select_row(widget, 0)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    widget._on_remove()
    assert project.config.score_definition_names() == ["Power"]
    stack.undo()
    assert project.config.score_definition_names() == ["Technique", "Power"]

    _accept_score_form(monkeypatch, ("Speed", "", 0.0, 1.0, "float"))
    widget._on_add()
    assert project.config.score_definition_names() == ["Technique", "Power", "Speed"]
    stack.undo()
    assert project.config.score_definition_names() == ["Technique", "Power"]


def test_toggle_scoring_enabled_is_undoable(project) -> None:
    stack = UndoStack()
    widget = _ScoresWidget(project, undo_stack=stack)
    assert project.config.scoring_enabled is False

    widget._enabled_checkbox.setChecked(True)
    assert project.config.scoring_enabled is True
    stack.undo()
    assert project.config.scoring_enabled is False
    stack.redo()
    assert project.config.scoring_enabled is True


def test_settings_dialog_hands_the_stack_to_both_tabs(project) -> None:
    from vat.ui.project_settings_dialog import ProjectSettingsDialog

    stack = UndoStack()
    dialog = ProjectSettingsDialog(project, undo_stack=stack)
    assert dialog.labels_widget._undo_stack is stack
    assert dialog.scores_widget._undo_stack is stack
