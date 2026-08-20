from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from vat.media.video_scanner import VideoInfo

ANNOTATED_COLOR = QColor("#3cb44b")
NOT_ANNOTATED_COLOR = QColor("#8a8a8a")


class PlaylistPanel(QWidget):
    """Left-hand panel: the videos directory acting as a playlist.

    Purely a view -- it knows nothing about Project/annotation logic. The
    controller (MainWindow) feeds it (VideoInfo, is_annotated) pairs and
    listens to `video_selected`.
    """

    video_selected = Signal(str)  # emits an absolute video path
    change_videos_dir_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths_by_row: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._choose_dir_btn = QPushButton("Choose Videos Directory…")
        self._choose_dir_btn.clicked.connect(self.change_videos_dir_requested)
        layout.addWidget(self._choose_dir_btn)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

    def set_videos(self, videos: list[VideoInfo], annotated_flags: dict[str, bool]) -> None:
        current_path = self.current_path()
        self._list.blockSignals(True)
        self._list.clear()
        self._paths_by_row = []
        restore_row = -1
        for video in videos:
            annotated = annotated_flags.get(video.rel_path, False)
            marker = "●" if annotated else "○"
            item = QListWidgetItem(f"{marker}  {video.rel_path}")
            item.setForeground(ANNOTATED_COLOR if annotated else NOT_ANNOTATED_COLOR)
            self._list.addItem(item)
            self._paths_by_row.append(video.path)
            if video.path == current_path:
                restore_row = len(self._paths_by_row) - 1
        self._list.blockSignals(False)
        if restore_row >= 0:
            self._list.setCurrentRow(restore_row)
        elif self._paths_by_row:
            self._list.setCurrentRow(0)

    def current_path(self) -> str | None:
        row = self._list.currentRow()
        if 0 <= row < len(self._paths_by_row):
            return self._paths_by_row[row]
        return None

    def next_path(self) -> str | None:
        row = self._list.currentRow()
        if 0 <= row + 1 < len(self._paths_by_row):
            return self._paths_by_row[row + 1]
        return None

    def select_path(self, path: str) -> None:
        if path in self._paths_by_row:
            self._list.setCurrentRow(self._paths_by_row.index(path))

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._paths_by_row):
            self.video_selected.emit(self._paths_by_row[row])
