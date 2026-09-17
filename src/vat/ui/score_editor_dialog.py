from __future__ import annotations

from typing import Self
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vat.errors import DuplicateScoreDefinitionError, ScoreDefinitionNotFoundError
from vat.models.score_definition import DTYPE_FLOAT, DTYPE_INT, VALID_DTYPES
from vat.project.project import Project
from vat.project.undo_stack import Command, UndoStack

_COLUMNS = ["Name", "Description", "Min", "Max", "Type"]
_SPIN_RANGE = 1_000_000_000


class _ScoreFormDialog(QDialog):
    """Add/edit form for a single score definition: name, description, range, dtype."""

    def __init__(
        self, parent: Self | None=None, name: str = "", description: str = "",
        minimum: float = 0.0, maximum: float = 100.0, dtype: str = DTYPE_FLOAT,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Score")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name_edit = QLineEdit(name)
        form.addRow("Name:", self._name_edit)

        self._description_edit = QLineEdit(description)
        self._description_edit.setPlaceholderText("What does this score mean?")
        form.addRow("Description:", self._description_edit)

        self._min_spin = QDoubleSpinBox()
        self._min_spin.setRange(-_SPIN_RANGE, _SPIN_RANGE)
        self._min_spin.setDecimals(4)
        self._min_spin.setValue(minimum)
        form.addRow("Minimum:", self._min_spin)

        self._max_spin = QDoubleSpinBox()
        self._max_spin.setRange(-_SPIN_RANGE, _SPIN_RANGE)
        self._max_spin.setDecimals(4)
        self._max_spin.setValue(maximum)
        form.addRow("Maximum:", self._max_spin)

        self._dtype_combo = QComboBox()
        self._dtype_combo.addItems(list(VALID_DTYPES))
        self._dtype_combo.setCurrentText(dtype)
        self._dtype_combo.currentTextChanged.connect(self._on_dtype_changed)
        form.addRow("Type:", self._dtype_combo)

        layout.addLayout(form)
        self._on_dtype_changed(dtype)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_dtype_changed(self, dtype: str) -> None:
        # Whole-number entry only for 'int' scores -- decimals=0 also rounds
        # any fractional value already typed, guiding the user toward a
        # valid combination before they even hit OK.
        decimals = 0 if dtype == DTYPE_INT else 4
        self._min_spin.setDecimals(decimals)
        self._max_spin.setDecimals(decimals)

    def values(self) -> tuple[str, str, float, float, str]:
        return (
            self._name_edit.text().strip(),
            self._description_edit.text().strip(),
            self._min_spin.value(),
            self._max_spin.value(),
            self._dtype_combo.currentText(),
        )


class _ScoresWidget(QWidget):
    """Enable/disable per-cut scoring for the project and manage the set of
    named score fields (each with its own range and dtype).

    Renaming a score propagates into every existing cut's scores dict via
    Project.rename_score_definition, mirroring label rename propagation.

    A plain QWidget (not QDialog) so it can be embedded both in the
    standalone ScoreEditorDialog below and as a tab in
    ProjectSettingsDialog.
    """

    def __init__(self, project: Project, parent: Self | None=None, undo_stack: UndoStack | None = None) -> None:
        super().__init__(parent)
        self._project = project
        self._undo_stack = undo_stack  # same contract as _LabelsWidget's

        layout = QVBoxLayout(self)

        self._enabled_checkbox = QCheckBox("Enable scoring for this project")
        self._enabled_checkbox.setChecked(project.config.scoring_enabled)
        self._enabled_checkbox.toggled.connect(self._on_toggle_enabled)
        layout.addWidget(self._enabled_checkbox)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
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

        self._refresh()

    def _on_toggle_enabled(self, checked: bool) -> None:
        if checked == self._project.config.scoring_enabled:
            return
        project = self._project
        project.set_scoring_enabled(checked)
        self._push(
            undo=lambda: project.set_scoring_enabled(not checked),
            redo=lambda: project.set_scoring_enabled(checked),
        )

    def _push(self, undo, redo) -> None:
        if self._undo_stack is not None:
            self._undo_stack.push(Command(undo=undo, redo=redo))

    def _refresh(self) -> None:
        definitions = self._project.config.score_definitions
        self._table.setRowCount(len(definitions))
        for row, defn in enumerate(definitions):
            name_item = QTableWidgetItem(defn.name)
            name_item.setData(Qt.ItemDataRole.UserRole, defn.name)
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, QTableWidgetItem(defn.description))
            self._table.setItem(row, 2, QTableWidgetItem(f"{defn.minimum:g}"))
            self._table.setItem(row, 3, QTableWidgetItem(f"{defn.maximum:g}"))
            self._table.setItem(row, 4, QTableWidgetItem(defn.dtype))

    def _selected_names(self) -> list[str]:
        rows = {index.row() for index in self._table.selectedIndexes()}
        names = []
        for row in rows:
            item = self._table.item(row, 0)
            if item is not None:
                names.append(item.data(Qt.ItemDataRole.UserRole))
        return names

    def _on_add(self) -> None:
        dialog = _ScoreFormDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, description, minimum, maximum, dtype = dialog.values()
            if not name:
                return
            try:
                definition = self._project.add_score_definition(name, minimum, maximum, dtype, description)
            except (DuplicateScoreDefinitionError, ValueError) as exc:
                QMessageBox.warning(self, "Cannot Add Score", str(exc))
                return
            project, index = self._project, self._project.score_definition_index(definition.name)
            self._push(
                undo=lambda: project.remove_score_definitions([definition.name]),
                redo=lambda: project.restore_score_definition(definition, index),
            )
            self._refresh()

    def _on_edit(self) -> None:
        names = self._selected_names()
        if not names:
            return
        old_name = names[0]
        definition = self._project.config.find_score_definition(old_name)
        if definition is None:
            return
        dialog = _ScoreFormDialog(
            self, name=definition.name, description=definition.description,
            minimum=definition.minimum, maximum=definition.maximum, dtype=definition.dtype,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name, new_description, minimum, maximum, dtype = dialog.values()
            if not new_name:
                return
            old = definition  # rename builds a new object, so this stays the pre-edit snapshot
            try:
                renamed = self._project.rename_score_definition(
                    old_name, new_name, minimum, maximum, dtype, new_description
                )
            except (DuplicateScoreDefinitionError, ScoreDefinitionNotFoundError, ValueError) as exc:
                QMessageBox.warning(self, "Cannot Edit Score", str(exc))
                return
            project, saved_name = self._project, renamed.name
            self._push(
                undo=lambda: project.rename_score_definition(
                    saved_name, old.name, old.minimum, old.maximum, old.dtype, old.description
                ),
                redo=lambda: project.rename_score_definition(
                    old.name, saved_name, minimum, maximum, dtype, new_description
                ),
            )
            self._refresh()

    def _on_remove(self) -> None:
        names = self._selected_names()
        if not names:
            return
        confirm = QMessageBox.question(
            self,
            "Remove Scores",
            f"Remove {len(names)} score(s)? Existing cuts keep any values already recorded for "
            "them, but the field will no longer be shown or required.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        project = self._project
        removed = [(project.score_definition_index(n), project.config.find_score_definition(n)) for n in names]
        removed = sorted((i, d) for i, d in removed if d is not None)
        project.remove_score_definitions(names)
        self._push(
            undo=lambda: [project.restore_score_definition(defn, index) for index, defn in removed],
            redo=lambda: project.remove_score_definitions(names),
        )
        self._refresh()


class ScoreEditorDialog(QDialog):
    """Standalone modal wrapper around _ScoresWidget -- just window chrome
    (title, size, Close button) around the same table/CRUD content that
    ProjectSettingsDialog embeds as its "Scores" tab.
    """

    def __init__(self, project: Project, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Scores")
        self.resize(560, 360)

        layout = QVBoxLayout(self)
        self.content = _ScoresWidget(project, self)
        layout.addWidget(self.content)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.accept)
        close_buttons.accepted.connect(self.accept)
        layout.addWidget(close_buttons)
