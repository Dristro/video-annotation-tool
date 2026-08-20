from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from vat.errors import ProjectAlreadyExistsError, ProjectNotFoundError
from vat.models.label import Label
from vat.project.project import Project
from vat.ui.label_editor_dialog import _LabelFormDialog


class NewProjectDialog(QDialog):
    """Collects project dir, videos dir, and an initial (editable-later) label set."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.resize(420, 400)
        self.project: Project | None = None
        self._labels: list[Label] = []

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
        self._labels_list = QListWidget()
        layout.addWidget(self._labels_list)
        label_btn_row = QHBoxLayout()
        add_label_btn = QPushButton("Add Label…")
        add_label_btn.clicked.connect(self._add_label)
        label_btn_row.addWidget(add_label_btn)
        remove_label_btn = QPushButton("Remove Selected")
        remove_label_btn.clicked.connect(self._remove_label)
        label_btn_row.addWidget(remove_label_btn)
        layout.addLayout(label_btn_row)

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
            name, shortcut = dialog.values()
            if name:
                self._labels.append(Label(name=name, shortcut=shortcut))
                self._labels_list.addItem(QListWidgetItem(f"{name}  [{shortcut}]" if shortcut else name))

    def _remove_label(self) -> None:
        row = self._labels_list.currentRow()
        if row >= 0:
            self._labels_list.takeItem(row)
            del self._labels[row]

    def _on_accept(self) -> None:
        project_dir = self._project_dir_edit.text().strip()
        videos_dir = self._videos_dir_edit.text().strip()
        if not project_dir or not videos_dir:
            QMessageBox.warning(self, "Missing Info", "Both a project directory and a videos directory are required.")
            return
        try:
            self.project = Project.create(project_dir, videos_dir, self._labels)
        except ProjectAlreadyExistsError as exc:
            QMessageBox.warning(self, "Project Already Exists", str(exc))
            return
        self.accept()


class ProjectDialog(QDialog):
    """Entry-point dialog: create a new project or open an existing one."""

    def __init__(self, parent=None):
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
        dialog = NewProjectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.project is not None:
            self.project = dialog.project
            self.accept()

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
