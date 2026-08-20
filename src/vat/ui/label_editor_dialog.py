from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QKeySequenceEdit,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from vat.errors import DuplicateLabelError, LabelNotFoundError
from vat.project.project import Project

_COLUMNS = ["#", "Name", "Description", "Shortcut"]


class _LabelFormDialog(QDialog):
    """Add/edit form for a single label: name, description, and a shortcut
    that can be a full key combo (e.g. Ctrl+Shift+G), not just one key.
    """

    def __init__(self, parent=None, name: str = "", description: str = "", shortcut: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Label")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name_edit = QLineEdit(name)
        self._description_edit = QLineEdit(description)
        self._shortcut_edit = QKeySequenceEdit(QKeySequence(shortcut))
        form.addRow("Name:", self._name_edit)
        form.addRow("Description:", self._description_edit)
        form.addRow("Shortcut:", self._shortcut_edit)
        layout.addLayout(form)

        clear_shortcut_btn = QPushButton("Clear Shortcut")
        clear_shortcut_btn.clicked.connect(self._shortcut_edit.clear)
        layout.addWidget(clear_shortcut_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str, str]:
        """Returns (name, description, shortcut). Shortcut is a QKeySequence
        text like "Ctrl+G", "" if none was captured.
        """
        return (
            self._name_edit.text().strip(),
            self._description_edit.text().strip(),
            self._shortcut_edit.keySequence().toString(),
        )


class LabelEditorDialog(QDialog):
    """Add / remove / edit the project's label set, shown as a table of
    index / name / description / shortcut.

    Editing a label's name propagates the rename into every existing cut in
    the annotations file via Project.rename_label, per REQUIREMENT.md.
    """

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self._project = project
        self.setWindowTitle("Edit Labels")
        self.resize(480, 340)

        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.doubleClicked.connect(self._on_edit)
        layout.addWidget(self._table)

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
        labels = self._project.config.labels
        self._table.setRowCount(len(labels))
        for row, label in enumerate(labels):
            index_item = QTableWidgetItem(str(row + 1))
            index_item.setData(Qt.ItemDataRole.UserRole, label.name)
            self._table.setItem(row, 0, index_item)
            self._table.setItem(row, 1, QTableWidgetItem(label.name))
            self._table.setItem(row, 2, QTableWidgetItem(label.description))
            self._table.setItem(row, 3, QTableWidgetItem(label.shortcut))

    def _selected_names(self) -> list[str]:
        rows = {index.row() for index in self._table.selectedIndexes()}
        names = []
        for row in rows:
            item = self._table.item(row, 0)
            if item is not None:
                names.append(item.data(Qt.ItemDataRole.UserRole))
        return names

    def _on_add(self) -> None:
        dialog = _LabelFormDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, description, shortcut = dialog.values()
            if not name:
                return
            try:
                self._project.add_label(name, shortcut, description)
            except DuplicateLabelError as exc:
                QMessageBox.warning(self, "Duplicate Label", str(exc))
                return
            self._refresh()

    def _on_edit(self) -> None:
        names = self._selected_names()
        if not names:
            return
        old_name = names[0]
        label = self._project.config.find_label(old_name)
        if label is None:
            return
        dialog = _LabelFormDialog(self, name=label.name, description=label.description, shortcut=label.shortcut)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name, new_description, new_shortcut = dialog.values()
            if not new_name:
                return
            try:
                self._project.rename_label(old_name, new_name, new_shortcut, new_description)
            except (DuplicateLabelError, LabelNotFoundError) as exc:
                QMessageBox.warning(self, "Cannot Edit Label", str(exc))
                return
            self._refresh()

    def _on_remove(self) -> None:
        names = self._selected_names()
        if not names:
            return
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
