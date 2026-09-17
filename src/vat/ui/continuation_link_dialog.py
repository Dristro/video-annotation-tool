from __future__ import annotations

import uuid

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from vat.models.cut import Cut
from vat.ui.video_panel import format_time


class ContinuationLinkDialog(QDialog):
    """Set or change an existing cut's cross-video continuation links.

    At creation time a link is made via the "Continues into next video"
    checkbox (front half) or the "Start Here" banner (back half). This
    dialog is the after-the-fact equivalent for a cut that already exists
    -- e.g. one whose link was broken, or one that was added before the
    user realised it continued -- and covers both directions at once,
    since a middle segment of a 3+-video chain is both:

    - **Continues into the next video** (front half): sets
      `continues_forward`, and the cut's end becomes the video's end,
      exactly as for a newly-added continuing cut.
    - **Completes an annotation from the previous video** (back half):
      pick which of the previous video's front halves this cut completes,
      or none. Only front halves not already completed by *another* cut
      in this video are offered (plus the one this cut already
      completes, if any).

    `resolve()` turns the choices into the `(continuation_id,
    continues_forward)` pair to store, reusing ids the same way
    MainWindow._on_add_cut() does: a completed link's id is carried
    forward when the cut also continues (one id per chain), and a cut that
    only continues forward keeps its existing forward id if it had one
    (so a back half already recorded in the next video stays attached)
    or gets a fresh one.
    """

    def __init__(
        self, cut: Cut, candidates: list[Cut], next_video_available: bool, previous_video_name: str | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Link Continuation")
        self._cut = cut
        self._candidates = list(candidates)

        layout = QVBoxLayout(self)
        summary = f"'{cut.label}' {format_time(cut.start)}–{format_time(cut.end)}" if cut.label else (
            f"{format_time(cut.start)}–{format_time(cut.end)}"
        )
        layout.addWidget(QLabel(f"Annotation: {summary}"))

        self._forward_checkbox = QCheckBox("Continues into the next video (end becomes this video's end)")
        self._forward_checkbox.setChecked(cut.continues_forward)
        self._forward_checkbox.setEnabled(next_video_available)
        if not next_video_available:
            self._forward_checkbox.setToolTip("There is no next video in the playlist to continue into.")
        layout.addWidget(self._forward_checkbox)

        title = "Completes an annotation from the previous video"
        if previous_video_name:
            title += f" ({previous_video_name})"
        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)
        self._none_radio = QRadioButton("None")
        group_layout.addWidget(self._none_radio)
        self._candidate_radios: list[QRadioButton] = []
        for candidate in self._candidates:
            label_part = f"'{candidate.label}' " if candidate.label else ""
            radio = QRadioButton(f"{label_part}{format_time(candidate.start)}–{format_time(candidate.end)}")
            self._candidate_radios.append(radio)
            group_layout.addWidget(radio)
        if not self._candidates:
            hint = QLabel("The previous video has no uncompleted continuing annotations.")
            hint.setWordWrap(True)
            group_layout.addWidget(hint)
        layout.addWidget(group)

        # Pre-select whatever this cut already completes (a back half's id
        # matches a candidate's), else None.
        current = next(
            (i for i, c in enumerate(self._candidates) if cut.continuation_id and c.continuation_id == cut.continuation_id),
            None,
        )
        if current is None:
            self._none_radio.setChecked(True)
        else:
            self._candidate_radios[current].setChecked(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- Results --------------------------------------------------------------
    def continues_forward(self) -> bool:
        return self._forward_checkbox.isChecked()

    def completes(self) -> Cut | None:
        for radio, candidate in zip(self._candidate_radios, self._candidates):
            if radio.isChecked():
                return candidate
        return None

    def resolve(self) -> tuple[str | None, bool]:
        """`(continuation_id, continues_forward)` to store for the cut."""
        return resolve_link(self._cut, self.completes(), self.continues_forward())


def resolve_link(cut: Cut, completes: Cut | None, continues_forward: bool) -> tuple[str | None, bool]:
    """Pure form of ContinuationLinkDialog.resolve(), for tests and for
    MainWindow; see the class docstring for the id-reuse rules."""
    if completes is not None:
        return completes.continuation_id, continues_forward
    if continues_forward:
        # Keep an existing forward id so a back half already recorded in
        # the next video stays attached; only mint one if there's none.
        existing = cut.continuation_id if cut.continues_forward else None
        return existing or uuid.uuid4().hex, True
    return None, False
