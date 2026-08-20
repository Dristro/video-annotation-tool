from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vat.models.cut import Cut
from vat.models.label import Label
from vat.models.score_definition import ScoreDefinition
from vat.ui.video_panel import format_time


class InspectorPanel(QWidget):
    """Right-hand panel: mark in/out, assign a label (+ scores, if the
    project has scoring enabled), manage cuts for the current video, and
    confirm the video as annotated.

    Pure view + signals; MainWindow owns all Project/annotation mutations.
    """

    mark_in_requested = Signal()
    mark_out_requested = Signal()
    add_cut_requested = Signal(str)  # label name
    delete_cut_requested = Signal(str)  # cut id
    seek_to_cut_requested = Signal(str)  # cut id
    set_annotated_requested = Signal(bool)
    edit_labels_requested = Signal()
    edit_scores_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending_in: float | None = None
        self._pending_out: float | None = None
        self._cuts_by_row: list[str] = []
        self._score_definitions: list[ScoreDefinition] = []
        self._score_inputs: dict[str, QLineEdit] = {}
        self._scoring_enabled = False

        layout = QVBoxLayout(self)

        self._video_name_label = QLabel("No video selected")
        self._video_name_label.setWordWrap(True)
        layout.addWidget(self._video_name_label)

        self._mark_group = QGroupBox("New Annotation")
        mark_layout = QVBoxLayout(self._mark_group)

        in_out_row = QHBoxLayout()
        self._mark_in_btn = QPushButton("Mark In (I)")
        self._mark_in_btn.clicked.connect(self.mark_in_requested)
        in_out_row.addWidget(self._mark_in_btn)
        self._mark_out_btn = QPushButton("Mark Out (O)")
        self._mark_out_btn.clicked.connect(self.mark_out_requested)
        in_out_row.addWidget(self._mark_out_btn)
        mark_layout.addLayout(in_out_row)

        self._pending_label = QLabel("In: -- / Out: --")
        mark_layout.addWidget(self._pending_label)

        label_row = QHBoxLayout()
        self._label_combo = QComboBox()
        label_row.addWidget(self._label_combo, stretch=1)
        edit_labels_btn = QPushButton("Edit Labels…")
        edit_labels_btn.clicked.connect(self.edit_labels_requested)
        label_row.addWidget(edit_labels_btn)
        mark_layout.addLayout(label_row)

        # Score input rows are built/torn down dynamically by
        # set_score_definitions() based on the project's current config --
        # this form layout is the container they get inserted into.
        self._scores_form = QFormLayout()
        mark_layout.addLayout(self._scores_form)

        self._score_error_label = QLabel("")
        self._score_error_label.setWordWrap(True)
        self._score_error_label.setStyleSheet("color: #b00020;")
        mark_layout.addWidget(self._score_error_label)

        edit_scores_btn = QPushButton("Edit Scores…")
        edit_scores_btn.clicked.connect(self.edit_scores_requested)
        mark_layout.addWidget(edit_scores_btn)

        self._add_cut_btn = QPushButton("Add Annotation")
        self._add_cut_btn.setEnabled(False)
        self._add_cut_btn.clicked.connect(self._emit_add_cut)
        mark_layout.addWidget(self._add_cut_btn)

        layout.addWidget(self._mark_group)

        cuts_group = QGroupBox("Cuts")
        cuts_layout = QVBoxLayout(cuts_group)
        self._cuts_list = QListWidget()
        self._cuts_list.itemDoubleClicked.connect(self._on_cut_double_clicked)
        cuts_layout.addWidget(self._cuts_list)
        delete_cut_btn = QPushButton("Delete Selected Cut")
        delete_cut_btn.clicked.connect(self._emit_delete_cut)
        cuts_layout.addWidget(delete_cut_btn)
        layout.addWidget(cuts_group)

        annotated_group = QGroupBox("Annotation Status")
        annotated_layout = QVBoxLayout(annotated_group)
        self._annotated_status_label = QLabel("Not annotated")
        annotated_layout.addWidget(self._annotated_status_label)
        annotated_row = QHBoxLayout()
        self._mark_annotated_btn = QPushButton("Mark Annotated")
        self._mark_annotated_btn.clicked.connect(lambda: self.set_annotated_requested.emit(True))
        annotated_row.addWidget(self._mark_annotated_btn)
        self._unmark_annotated_btn = QPushButton("Unmark Annotated")
        self._unmark_annotated_btn.clicked.connect(lambda: self.set_annotated_requested.emit(False))
        annotated_row.addWidget(self._unmark_annotated_btn)
        annotated_layout.addLayout(annotated_row)
        layout.addWidget(annotated_group)

        layout.addStretch(1)

    # -- Population from controller ------------------------------------------------
    def set_video_name(self, name: str | None) -> None:
        self._video_name_label.setText(name or "No video selected")

    def set_labels(self, labels: list[Label]) -> None:
        current = self._label_combo.currentText()
        self._label_combo.blockSignals(True)
        self._label_combo.clear()
        for label in labels:
            display = f"{label.name} ({label.shortcut})" if label.shortcut else label.name
            self._label_combo.addItem(display, userData=label.name)
        self._label_combo.blockSignals(False)
        idx = self._label_combo.findData(current)
        if idx >= 0:
            self._label_combo.setCurrentIndex(idx)

    def selected_label_name(self) -> str:
        return self._label_combo.currentData() or ""

    def select_label(self, name: str) -> None:
        idx = self._label_combo.findData(name)
        if idx >= 0:
            self._label_combo.setCurrentIndex(idx)

    def set_score_definitions(self, scoring_enabled: bool, definitions: list[ScoreDefinition]) -> None:
        """(Re)build the dynamic score input rows. Called on load, on
        project switch, and whenever score definitions are edited -- the
        set of fields (and their ranges/dtypes) can change at any time.
        """
        self._scoring_enabled = scoring_enabled
        self._score_definitions = list(definitions)

        while self._scores_form.rowCount():
            self._scores_form.removeRow(0)
        self._score_inputs.clear()

        if scoring_enabled:
            for defn in self._score_definitions:
                edit = QLineEdit()
                edit.setPlaceholderText(f"{defn.minimum:g}–{defn.maximum:g}")
                validator = QDoubleValidator(defn.minimum, defn.maximum, 6, edit)
                validator.setNotation(QDoubleValidator.Notation.StandardNotation)
                edit.setValidator(validator)
                edit.textChanged.connect(self._refresh_add_button_state)
                self._scores_form.addRow(f"{defn.name}:", edit)
                self._score_inputs[defn.name] = edit

        self._refresh_add_button_state()

    def pending_scores(self) -> dict[str, float]:
        """Coerced, validated score values. Only meaningful when the Add
        Annotation button is enabled -- invalid/empty fields are simply
        omitted rather than raising, since MainWindow only calls this from
        the button's own click handler.
        """
        result: dict[str, float] = {}
        for defn in self._score_definitions:
            edit = self._score_inputs.get(defn.name)
            if edit is None:
                continue
            try:
                result[defn.name] = defn.coerce(edit.text())
            except ValueError:
                continue
        return result

    def set_pending_in(self, seconds: float | None) -> None:
        self._pending_in = seconds
        self._refresh_pending_label()

    def set_pending_out(self, seconds: float | None) -> None:
        self._pending_out = seconds
        self._refresh_pending_label()

    def pending_in(self) -> float | None:
        return self._pending_in

    def pending_out(self) -> float | None:
        return self._pending_out

    def clear_pending(self) -> None:
        self._pending_in = None
        self._pending_out = None
        for edit in self._score_inputs.values():
            edit.clear()
        self._refresh_pending_label()

    def _refresh_pending_label(self) -> None:
        in_text = format_time(self._pending_in) if self._pending_in is not None else "--"
        out_text = format_time(self._pending_out) if self._pending_out is not None else "--"
        self._pending_label.setText(f"In: {in_text} / Out: {out_text}")
        self._refresh_add_button_state()

    def _refresh_add_button_state(self) -> None:
        in_out_valid = (
            self._pending_in is not None
            and self._pending_out is not None
            and self._pending_out > self._pending_in
        )
        scores_valid = True
        error = ""
        if self._scoring_enabled:
            for defn in self._score_definitions:
                edit = self._score_inputs.get(defn.name)
                if edit is None:
                    continue
                try:
                    defn.coerce(edit.text())
                except ValueError as exc:
                    scores_valid = False
                    if not error:
                        error = str(exc)
        self._score_error_label.setText(error)
        self._add_cut_btn.setEnabled(in_out_valid and scores_valid)

    def set_cuts(self, cuts: list[Cut], score_definitions: list[ScoreDefinition], scoring_enabled: bool) -> None:
        self._cuts_list.clear()
        self._cuts_by_row = []
        for cut in cuts:
            label_part = f" [{cut.label}]" if cut.label else ""
            scores_part = ""
            if cut.scores:
                scores_part = "  " + ", ".join(f"{name}={value:g}" for name, value in cut.scores.items())
            missing = (
                [d.name for d in score_definitions if d.name not in cut.scores] if scoring_enabled else []
            )
            incomplete_part = f"  ⚠ missing: {', '.join(missing)}" if missing else ""
            text = f"{format_time(cut.start)} – {format_time(cut.end)}{label_part}{scores_part}{incomplete_part}"
            item = QListWidgetItem(text)
            self._cuts_list.addItem(item)
            self._cuts_by_row.append(cut.id)

    def set_annotated(self, annotated: bool, has_entry: bool) -> None:
        if annotated:
            self._annotated_status_label.setText("Annotated ✓")
        elif has_entry:
            self._annotated_status_label.setText("In progress (not yet confirmed)")
        else:
            self._annotated_status_label.setText("Not annotated")
        self._mark_annotated_btn.setEnabled(not annotated)
        self._unmark_annotated_btn.setEnabled(annotated)

    def selected_cut_id(self) -> str | None:
        row = self._cuts_list.currentRow()
        if 0 <= row < len(self._cuts_by_row):
            return self._cuts_by_row[row]
        return None

    # -- Internal signal glue ------------------------------------------------
    def _emit_add_cut(self) -> None:
        self.add_cut_requested.emit(self.selected_label_name())

    def _emit_delete_cut(self) -> None:
        cut_id = self.selected_cut_id()
        if cut_id:
            self.delete_cut_requested.emit(cut_id)

    def _on_cut_double_clicked(self, item: QListWidgetItem) -> None:
        row = self._cuts_list.row(item)
        if 0 <= row < len(self._cuts_by_row):
            self.seek_to_cut_requested.emit(self._cuts_by_row[row])

    def select_cut_by_id(self, cut_id: str) -> None:
        if cut_id in self._cuts_by_row:
            self._cuts_list.setCurrentRow(self._cuts_by_row.index(cut_id))
