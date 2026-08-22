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
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vat.errors import DuplicateLabelError, LabelNotFoundError
from vat.project.project import Project
from vat.ui.widgets import SingleStrokeKeySequenceEdit

_COLUMNS = ["#", "Name", "Description", "Shortcut"]

STROKE_SEPARATOR = ", "  # how QKeySequence renders/parses a multi-stroke sequence


def split_strokes(shortcut: str) -> tuple[str, str]:
    """Split a stored shortcut into its first and (optional) second stroke.

    Anything beyond two strokes is dropped -- the form only offers two, and
    nothing in this app needs a three-key sequence.
    """
    strokes = shortcut.split(STROKE_SEPARATOR) if shortcut else []
    return (
        strokes[0] if strokes else "",
        strokes[1] if len(strokes) > 1 else "",
    )


def join_strokes(first: str, second: str) -> str:
    if not first:
        return ""  # a second stroke on its own is meaningless
    return f"{first}{STROKE_SEPARATOR}{second}" if second else first


def describe_shortcut(shortcut: str) -> str:
    """Plain-English description of what a recorded shortcut will do, shown
    live under the shortcut fields.

    A two-key sequence ("S, L") used to be indistinguishable from a single
    combo in this form, which is how users ended up with one by accident
    and then couldn't work out why neither key did anything on its own.
    Spelling it out is what makes the difference visible.
    """
    first, second = split_strokes(shortcut)
    if not first:
        return "No shortcut — this label can only be picked from the list."
    if not second:
        return f"Single key: press {first}."
    return f"Two-key sequence: press {first}, then {second} — one after the other, not together."


class _LabelFormDialog(QDialog):
    """Add/edit form for a single label: name, description, and a shortcut
    that can be a full key combo (e.g. Ctrl+Shift+G) or a two-key sequence
    (e.g. S then L), not just one key.

    The two-key case gets its own second field rather than being recorded
    by pressing two keys into one QKeySequenceEdit. Qt's own widget does
    support that, but it accumulates *silently* -- pressing Ctrl+G and then
    Ctrl+Shift+G to correct it records the two-step sequence "Ctrl+G,
    Ctrl+Shift+G" rather than replacing, which was reported as a real bug
    (neither combo alone worked afterwards, with nothing in the UI hinting
    why). With two single-stroke fields, correcting either stroke can never
    silently lengthen the sequence, and asking for a second stroke is
    always something the user did on purpose.
    """

    def __init__(self, parent=None, name: str = "", description: str = "", shortcut: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Label")
        first, second = split_strokes(shortcut)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name_edit = QLineEdit(name)
        self._description_edit = QLineEdit(description)
        self._shortcut_edit = SingleStrokeKeySequenceEdit(QKeySequence(first))
        self._second_stroke_edit = SingleStrokeKeySequenceEdit(QKeySequence(second))
        form.addRow("Name:", self._name_edit)
        form.addRow("Description:", self._description_edit)
        form.addRow("Shortcut:", self._shortcut_edit)
        form.addRow("Then (optional):", self._second_stroke_edit)
        layout.addLayout(form)

        self._shortcut_hint = QLabel()
        self._shortcut_hint.setWordWrap(True)
        self._shortcut_hint.setEnabled(False)  # de-emphasized, this is a hint not a field
        layout.addWidget(self._shortcut_hint)
        self._shortcut_edit.keySequenceChanged.connect(self._refresh_shortcut_hint)
        self._second_stroke_edit.keySequenceChanged.connect(self._refresh_shortcut_hint)
        self._refresh_shortcut_hint()

        clear_shortcut_btn = QPushButton("Clear Shortcut")
        clear_shortcut_btn.clicked.connect(self._clear_shortcut)
        layout.addWidget(clear_shortcut_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _clear_shortcut(self) -> None:
        self._shortcut_edit.clear()
        self._second_stroke_edit.clear()

    def _shortcut(self) -> str:
        return join_strokes(
            self._shortcut_edit.keySequence().toString(),
            self._second_stroke_edit.keySequence().toString(),
        )

    def _refresh_shortcut_hint(self) -> None:
        self._shortcut_hint.setText(describe_shortcut(self._shortcut()))

    def values(self) -> tuple[str, str, str]:
        """Returns (name, description, shortcut). Shortcut is a QKeySequence
        text like "Ctrl+G" or "S, L", "" if none was captured.
        """
        return (
            self._name_edit.text().strip(),
            self._description_edit.text().strip(),
            self._shortcut(),
        )


class _LabelsWidget(QWidget):
    """Add / remove / edit the project's label set, shown as a table of
    index / name / description / shortcut.

    Editing a label's name propagates the rename into every existing cut in
    the annotations file via Project.rename_label, per REQUIREMENT.md.

    A plain QWidget (not QDialog) so it can be embedded both in the
    standalone LabelEditorDialog below and as a tab in
    ProjectSettingsDialog -- the table/CRUD logic is identical either way,
    only the surrounding chrome (window title, Close button) differs.
    """

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self._project = project

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

    def _warn_if_shortcut_collides(self, shortcut: str, excluding_name: str | None = None) -> None:
        """Non-blocking heads-up: two labels sharing a shortcut isn't
        rejected (the shortcut field is otherwise freeform), but only one
        QShortcut can ever fire for a given key combo -- whichever label
        was registered last in MainWindow._register_label_shortcuts()
        silently wins and the other's shortcut just never fires. Warn so
        the user finds out here rather than by a shortcut mysteriously not
        working later.
        """
        if not shortcut:
            return
        others = [label for label in self._project.config.labels if label.name != excluding_name]
        colliding = [label.name for label in others if label.shortcut == shortcut]
        if colliding:
            QMessageBox.warning(
                self,
                "Duplicate Shortcut",
                f"'{shortcut}' is already used by: {', '.join(colliding)}. "
                "Only one label's shortcut will actually respond to the key.",
            )
            return
        # A shortcut that is the *start* of a longer one (e.g. "S" and
        # "S, L") is fully supported, but the shorter one can't fire until
        # it's clear the longer one isn't coming -- so it waits out a brief
        # delay. Worth saying out loud rather than leaving it to be noticed
        # as sluggishness.
        starts = sorted(label.shortcut for label in others if label.shortcut.startswith(shortcut + ", "))
        started_by = sorted(
            label.shortcut for label in others if label.shortcut and shortcut.startswith(label.shortcut + ", ")
        )
        if starts or started_by:
            shorter = shortcut if starts else started_by[0]
            longer = ", ".join("'%s'" % s for s in (starts or [shortcut]))
            QMessageBox.information(
                self,
                "Shortcut Starts Another",
                f"'{shorter}' is also the start of {longer}. "
                f"Both work, but '{shorter}' on its own takes effect a moment later, "
                "once it's clear the longer sequence isn't being typed.",
            )

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
            self._warn_if_shortcut_collides(shortcut, excluding_name=name)
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
            self._warn_if_shortcut_collides(new_shortcut, excluding_name=new_name)
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


class LabelEditorDialog(QDialog):
    """Standalone modal wrapper around _LabelsWidget -- just window chrome
    (title, size, Close button) around the same table/CRUD content that
    ProjectSettingsDialog embeds as its "Labels" tab.
    """

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Labels")
        self.resize(480, 340)

        layout = QVBoxLayout(self)
        self.content = _LabelsWidget(project, self)
        layout.addWidget(self.content)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.accept)
        close_buttons.accepted.connect(self.accept)
        layout.addWidget(close_buttons)
