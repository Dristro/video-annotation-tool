import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.project.project import Project  # noqa: E402
from vat.ui.project_settings_dialog import ProjectSettingsDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def project(qapp, tmp_project_dir, tmp_videos_dir):
    p = Project.create(tmp_project_dir, tmp_videos_dir)
    p.add_label("goal", shortcut="Ctrl+G")
    p.add_score_definition("Technique", 0, 100)
    return p


def test_has_labels_and_scores_tabs(project):
    dialog = ProjectSettingsDialog(project)
    assert dialog._tabs.count() == 2
    assert dialog._tabs.tabText(0) == "Labels"
    assert dialog._tabs.tabText(1) == "Scores"


def test_defaults_to_labels_tab(project):
    dialog = ProjectSettingsDialog(project)
    assert dialog._tabs.currentIndex() == 0


def test_initial_tab_scores_selects_scores_tab(project):
    dialog = ProjectSettingsDialog(project, initial_tab="scores")
    assert dialog._tabs.currentIndex() == 1


def test_labels_tab_reflects_project_labels(project):
    dialog = ProjectSettingsDialog(project)
    assert dialog.labels_widget._table.rowCount() == 1
    assert dialog.labels_widget._table.item(0, 1).text() == "goal"


def test_scores_tab_reflects_project_score_definitions(project):
    dialog = ProjectSettingsDialog(project)
    assert dialog.scores_widget._table.rowCount() == 1
    assert dialog.scores_widget._table.item(0, 0).text() == "Technique"
