from __future__ import annotations

from typing import Self
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from vat.errors import ProjectAlreadyExistsError, ProjectNotFoundError
from vat.models.label import Label
from vat.models.score_definition import ScoreDefinition
from vat.project.project import Project
from vat.ui.label_editor_dialog import _LabelFormDialog
from vat.ui.score_editor_dialog import _ScoreFormDialog


class NewProjectDialog(QDialog):
    """Collects project dir, videos dir, and an initial (editable-later) label set."""

    def __init__(self, parent: Self | None=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.resize(420, 400)
        self.project: Project | None = None
        self._labels: list[Label] = []
        self._score_definitions: list[ScoreDefinition] = []

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Project directory (where project files are saved):"))
        proj_row = QHBoxLayout()
        self._project_dir_edit = QLineEdit()
        proj_row.addWidget(self._project_dir_edit)
        proj_browse = QPushButton("Browse…")
        proj_browse.clicked.connect(self._browse_project_dir)
        proj_row.addWidget(proj_browse)
        layout.addLayout(proj_row)

        layout.addWidget(QLabel("Videos directory (source videos to annotate):"))
        vid_row = QHBoxLayout()
        self._videos_dir_edit = QLineEdit()
        vid_row.addWidget(self._videos_dir_edit)
        vid_browse = QPushButton("Browse…")
        vid_browse.clicked.connect(self._browse_videos_dir)
        vid_row.addWidget(vid_browse)
        layout.addLayout(vid_row)

        layout.addWidget(QLabel("Initial labels (can be edited later):"))
        self._labels_table = QTableWidget(0, 3)
        self._labels_table.setHorizontalHeaderLabels(["Name", "Description", "Shortcut"])
        self._labels_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._labels_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._labels_table.verticalHeader().setVisible(False)
        header = self._labels_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._labels_table)
        label_btn_row = QHBoxLayout()
        add_label_btn = QPushButton("Add Label…")
        add_label_btn.clicked.connect(self._add_label)
        label_btn_row.addWidget(add_label_btn)
        remove_label_btn = QPushButton("Remove Selected")
        remove_label_btn.clicked.connect(self._remove_label)
        label_btn_row.addWidget(remove_label_btn)
        layout.addLayout(label_btn_row)

        # Scoring is entirely optional (project-level, per REQUIREMENT.md
        # #9) -- consistent with labels being editable-later, everything
        # set up here can also be changed afterwards via Edit > Edit
        # Scores…. This just closes the creation-time inconsistency where
        # only labels (not scores) could be set up at New Project time.
        self._scoring_checkbox = QCheckBox("Enable scoring for this project")
        self._scoring_checkbox.toggled.connect(self._on_scoring_toggled)
        layout.addWidget(self._scoring_checkbox)

        self._scores_table = QTableWidget(0, 5)
        self._scores_table.setHorizontalHeaderLabels(["Name", "Description", "Min", "Max", "Type"])
        self._scores_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._scores_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._scores_table.verticalHeader().setVisible(False)
        self._scores_table.setEnabled(False)
        header = self._scores_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._scores_table)
        score_btn_row = QHBoxLayout()
        self._add_score_btn = QPushButton("Add Score…")
        self._add_score_btn.setEnabled(False)
        self._add_score_btn.clicked.connect(self._add_score)
        score_btn_row.addWidget(self._add_score_btn)
        self._remove_score_btn = QPushButton("Remove Selected")
        self._remove_score_btn.setEnabled(False)
        self._remove_score_btn.clicked.connect(self._remove_score)
        score_btn_row.addWidget(self._remove_score_btn)
        layout.addLayout(score_btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_project_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose Project Directory")
        if path:
            self._project_dir_edit.setText(path)

    def _browse_videos_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose Videos Directory")
        if path:
            self._videos_dir_edit.setText(path)

    def _add_label(self) -> None:
        dialog = _LabelFormDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, description, shortcut = dialog.values()
            if not name:
                return
            self._labels.append(Label(name=name, shortcut=shortcut, description=description))
            self._refresh_labels_table()

    def _remove_label(self) -> None:
        row = self._labels_table.currentRow()
        if row >= 0:
            del self._labels[row]
            self._refresh_labels_table()

    def _refresh_labels_table(self) -> None:
        self._labels_table.setRowCount(len(self._labels))
        for row, label in enumerate(self._labels):
            self._labels_table.setItem(row, 0, QTableWidgetItem(label.name))
            self._labels_table.setItem(row, 1, QTableWidgetItem(label.description))
            self._labels_table.setItem(row, 2, QTableWidgetItem(label.shortcut))

    def _on_scoring_toggled(self, checked: bool) -> None:
        self._scores_table.setEnabled(checked)
        self._add_score_btn.setEnabled(checked)
        self._remove_score_btn.setEnabled(checked)

    def _add_score(self) -> None:
        dialog = _ScoreFormDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, description, minimum, maximum, dtype = dialog.values()
            if not name:
                return
            try:
                self._score_definitions.append(
                    ScoreDefinition(name=name, minimum=minimum, maximum=maximum, dtype=dtype, description=description)
                )
            except ValueError as exc:
                QMessageBox.warning(self, "Cannot Add Score", str(exc))
                return
            self._refresh_scores_table()

    def _remove_score(self) -> None:
        row = self._scores_table.currentRow()
        if row >= 0:
            del self._score_definitions[row]
            self._refresh_scores_table()

    def _refresh_scores_table(self) -> None:
        self._scores_table.setRowCount(len(self._score_definitions))
        for row, defn in enumerate(self._score_definitions):
            self._scores_table.setItem(row, 0, QTableWidgetItem(defn.name))
            self._scores_table.setItem(row, 1, QTableWidgetItem(defn.description))
            self._scores_table.setItem(row, 2, QTableWidgetItem(f"{defn.minimum:g}"))
            self._scores_table.setItem(row, 3, QTableWidgetItem(f"{defn.maximum:g}"))
            self._scores_table.setItem(row, 4, QTableWidgetItem(defn.dtype))

    def _on_accept(self) -> None:
        project_dir = self._project_dir_edit.text().strip()
        videos_dir = self._videos_dir_edit.text().strip()
        if not project_dir or not videos_dir:
            QMessageBox.warning(self, "Missing Info", "Both a project directory and a videos directory are required.")
            return
        try:
            self.project = Project.create(
                project_dir, videos_dir, self._labels,
                scoring_enabled=self._scoring_checkbox.isChecked(),
                score_definitions=self._score_definitions,
            )
        except ProjectAlreadyExistsError as exc:
            QMessageBox.warning(self, "Project Already Exists", str(exc))
            return
        self.accept()


class ProjectDialog(QDialog):
    """Entry-point dialog: create a new project or open an existing one."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Video Annotation Tool")
        self.setModal(True)
        self.project: Project | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Welcome. Create a new project or open an existing one."))

        new_btn = QPushButton("New Project…")
        new_btn.clicked.connect(self._on_new)
        layout.addWidget(new_btn)

        open_btn = QPushButton("Open Existing Project…")
        open_btn.clicked.connect(self._on_open)
        layout.addWidget(open_btn)

        quit_btn = QPushButton("Quit")
        quit_btn.clicked.connect(self.reject)
        layout.addWidget(quit_btn)

    def _on_new(self) -> None:
        # Hide while NewProjectDialog (which itself opens native folder
        # pickers) is up: leaving this dialog visible+modal underneath
        # stacks three modal sessions (this -> NewProjectDialog -> native
        # panel), which macOS logs as "modalSession has been exited
        # prematurely". Two levels is fine; three isn't.
        self.hide()
        dialog = NewProjectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.project is not None:
            self.project = dialog.project
            self.accept()
        else:
            self.show()

    def _on_open(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose Project Directory")
        if not path:
            return
        try:
            self.project = Project.open(path)
        except ProjectNotFoundError as exc:
            QMessageBox.warning(self, "Not a Project", str(exc))
            return
        self.accept()
