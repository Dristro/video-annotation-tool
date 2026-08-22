from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QVBoxLayout

from vat.project.project import Project
from vat.ui.label_editor_dialog import _LabelsWidget
from vat.ui.score_editor_dialog import _ScoresWidget


class ProjectSettingsDialog(QDialog):
    """Single project-level settings surface: labels + scores as tabs.

    Replaces having "Edit Labels…" and "Edit Scores…" as two separate
    dialogs/menu items with no single project-settings surface
    (BACKLOG.md) -- videos dir / project dir are still their own menu
    entries (changing them is a filesystem operation, not "editing
    project settings" the way labels/scores are), but labels and scores
    are conceptually the same kind of thing (a project-level config list
    with add/edit/remove/rename) and now share one dialog.
    """

    def __init__(self, project: Project, parent=None, initial_tab: str = "labels"):
        super().__init__(parent)
        self.setWindowTitle("Project Settings")
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self.labels_widget = _LabelsWidget(project, self)
        self.scores_widget = _ScoresWidget(project, self)
        self._tabs.addTab(self.labels_widget, "Labels")
        self._tabs.addTab(self.scores_widget, "Scores")
        self._tabs.setCurrentIndex(1 if initial_tab == "scores" else 0)
        layout.addWidget(self._tabs)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.accept)
        close_buttons.accepted.connect(self.accept)
        layout.addWidget(close_buttons)
