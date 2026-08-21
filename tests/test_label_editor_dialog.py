import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from vat.project.project import Project  # noqa: E402
from vat.ui.label_editor_dialog import LabelEditorDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def project(qapp, tmp_project_dir, tmp_videos_dir):
    p = Project.create(tmp_project_dir, tmp_videos_dir)
    p.add_label("goal", shortcut="Ctrl+G")
    return p


def test_warn_if_shortcut_collides_flags_other_label_with_same_shortcut(project, monkeypatch):
    dialog = LabelEditorDialog(project)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok
    )

    dialog._warn_if_shortcut_collides("Ctrl+G", excluding_name="foul")

    assert len(warnings) == 1


def test_warn_if_shortcut_collides_silent_when_unique(project, monkeypatch):
    dialog = LabelEditorDialog(project)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok
    )

    dialog._warn_if_shortcut_collides("Ctrl+F", excluding_name="foul")

    assert warnings == []


def test_warn_if_shortcut_collides_excludes_own_label(project, monkeypatch):
    # Editing "goal" itself and keeping its own shortcut must not warn against itself.
    dialog = LabelEditorDialog(project)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok
    )

    dialog._warn_if_shortcut_collides("Ctrl+G", excluding_name="goal")

    assert warnings == []
