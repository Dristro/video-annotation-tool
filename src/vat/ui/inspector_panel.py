from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vat.models.cut import Cut
from vat.models.label import Label
from vat.ui.video_panel import format_time


class InspectorPanel(QWidget):
    """Right-hand panel: mark in/out, assign a label, manage cuts for the
    current video, and confirm the video as annotated.

    Pure view + signals; MainWindow owns all Project/annotation mutations.
    """

    mark_in_requested = Signal()
    mark_out_requested = Signal()
    add_cut_requested = Signal(str)  # label name
    delete_cut_requested = Signal(str)  # cut id
    seek_to_cut_requested = Signal(str)  # cut id
    set_annotated_requested = Signal(bool)
    edit_labels_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending_in: float | None = None
        self._pending_out: float | None = None
        self._cuts_by_row: list[str] = []

        layout = QVBoxLayout(self)

        self._video_name_label = QLabel("No video selected")
        self._video_name_label.setWordWrap(True)
        layout.addWidget(self._video_name_label)

        mark_group = QGroupBox("New Cut")
        mark_layout = QVBoxLayout(mark_group)

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

        self._add_cut_btn = QPushButton("Add Cut")
        self._add_cut_btn.setEnabled(False)
        self._add_cut_btn.clicked.connect(self._emit_add_cut)
        mark_layout.addWidget(self._add_cut_btn)

        layout.addWidget(mark_group)

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
        self._refresh_pending_label()

    def _refresh_pending_label(self) -> None:
        in_text = format_time(self._pending_in) if self._pending_in is not None else "--"
        out_text = format_time(self._pending_out) if self._pending_out is not None else "--"
        self._pending_label.setText(f"In: {in_text} / Out: {out_text}")
        valid = (
            self._pending_in is not None
            and self._pending_out is not None
            and self._pending_out > self._pending_in
        )
        self._add_cut_btn.setEnabled(valid)

    def set_cuts(self, cuts: list[Cut]) -> None:
        self._cuts_list.clear()
        self._cuts_by_row = []
        for cut in cuts:
            label_part = f" [{cut.label}]" if cut.label else ""
            item = QListWidgetItem(f"{format_time(cut.start)} – {format_time(cut.end)}{label_part}")
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
