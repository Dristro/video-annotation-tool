from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from vat.errors import DuplicateLabelError, LabelNotFoundError
from vat.project.project import Project


class _LabelFormDialog(QDialog):
    """Small add/edit form for a single label's name + shortcut."""

    def __init__(self, parent=None, name: str = "", shortcut: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Label")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name_edit = QLineEdit(name)
        self._shortcut_edit = QLineEdit(shortcut)
        self._shortcut_edit.setMaxLength(1)
        form.addRow("Name:", self._name_edit)
        form.addRow("Shortcut key:", self._shortcut_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str]:
        return self._name_edit.text().strip(), self._shortcut_edit.text().strip()


class LabelEditorDialog(QDialog):
    """Add / remove / edit the project's label set.

    Editing a label's name propagates the rename into every existing cut in
    the annotations file via Project.rename_label, per REQUIREMENT.md.
    """

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self._project = project
        self.setWindowTitle("Edit Labels")
        self.resize(360, 320)

        layout = QVBoxLayout(self)
        self._list = QListWidget()
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add…")
        add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(add_btn)
        edit_btn = QPushButton("Edit…")
        edit_btn.clicked.connect(self._on_edit)
        btn_row.addWidget(edit_btn)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._on_remove)
        btn_row.addWidget(remove_btn)
        layout.addLayout(btn_row)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.accept)
        close_buttons.accepted.connect(self.accept)
        layout.addWidget(close_buttons)

        self._refresh()

    def _refresh(self) -> None:
        self._list.clear()
        for label in self._project.config.labels:
            text = f"{label.name}  [{label.shortcut}]" if label.shortcut else label.name
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, label.name)
            self._list.addItem(item)

    def _on_add(self) -> None:
        dialog = _LabelFormDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, shortcut = dialog.values()
            if not name:
                return
            try:
                self._project.add_label(name, shortcut)
            except DuplicateLabelError as exc:
                QMessageBox.warning(self, "Duplicate Label", str(exc))
                return
            self._refresh()

    def _on_edit(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        old_name = item.data(Qt.ItemDataRole.UserRole)
        label = self._project.config.find_label(old_name)
        if label is None:
            return
        dialog = _LabelFormDialog(self, name=label.name, shortcut=label.shortcut)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name, new_shortcut = dialog.values()
            if not new_name:
                return
            try:
                self._project.rename_label(old_name, new_name, new_shortcut)
            except (DuplicateLabelError, LabelNotFoundError) as exc:
                QMessageBox.warning(self, "Cannot Edit Label", str(exc))
                return
            self._refresh()

    def _on_remove(self) -> None:
        selected_items = self._list.selectedItems()
        if not selected_items:
            return
        names = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        confirm = QMessageBox.question(
            self,
            "Remove Labels",
            f"Remove {len(names)} label(s)? Existing cuts keep their label text, "
            "but it will no longer be selectable.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._project.remove_labels(names)
        self._refresh()
