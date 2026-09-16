from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.models.score_definition import ScoreDefinition  # noqa: E402
from vat.ui.project_dialog import NewProjectDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication | QCoreApplication:
    return QApplication.instance() or QApplication([])


def test_scoring_controls_disabled_until_checkbox_checked(qapp) -> None:
    dialog = NewProjectDialog()
    assert dialog._scores_table.isEnabled() is False
    assert dialog._add_score_btn.isEnabled() is False

    dialog._scoring_checkbox.setChecked(True)
    assert dialog._scores_table.isEnabled() is True
    assert dialog._add_score_btn.isEnabled() is True


def test_accept_creates_project_with_initial_scores(qapp, tmp_project_dir, tmp_videos_dir) -> None:
    dialog = NewProjectDialog()
    dialog._project_dir_edit.setText(tmp_project_dir)
    dialog._videos_dir_edit.setText(tmp_videos_dir)
    dialog._scoring_checkbox.setChecked(True)
    dialog._score_definitions.append(ScoreDefinition(name="Technique", minimum=0, maximum=100))
    dialog._refresh_scores_table()

    dialog._on_accept()

    assert dialog.project is not None
    assert dialog.project.config.scoring_enabled is True
    assert dialog.project.config.score_definition_names() == ["Technique"]
