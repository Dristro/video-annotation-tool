from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from vat.media.video_scanner import VideoInfo

ANNOTATED_COLOR = QColor("#3cb44b")
NOT_ANNOTATED_COLOR = QColor("#8a8a8a")
THUMBNAIL_ICON_SIZE = QSize(80, 45)  # 16:9, matches media.thumbnails.THUMBNAIL_WIDTH's aspect roughly


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
        self._rel_paths_by_row: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._choose_dir_btn = QPushButton("Choose Videos Directory…")
        self._choose_dir_btn.clicked.connect(self.change_videos_dir_requested)
        layout.addWidget(self._choose_dir_btn)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setIconSize(THUMBNAIL_ICON_SIZE)
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

    def set_videos(
        self, videos: list[VideoInfo], annotated_flags: dict[str, bool], cut_counts: dict[str, int] | None = None,
        thumbnails: dict[str, str] | None = None,
    ) -> None:
        cut_counts = cut_counts or {}
        thumbnails = thumbnails or {}
        previous_path = self.current_path()
        self._list.blockSignals(True)
        self._list.clear()
        self._paths_by_row = []
        self._rel_paths_by_row = []
        restore_row = -1
        for video in videos:
            annotated = annotated_flags.get(video.rel_path, False)
            marker = "●" if annotated else "○"
            count = cut_counts.get(video.rel_path, 0)
            count_part = f"  ({count})" if count else ""
            item = QListWidgetItem(f"{marker}  {video.rel_path}{count_part}")
            item.setForeground(ANNOTATED_COLOR if annotated else NOT_ANNOTATED_COLOR)
            thumbnail_path = thumbnails.get(video.rel_path)
            if thumbnail_path:
                item.setIcon(QIcon(thumbnail_path))
            self._list.addItem(item)
            self._paths_by_row.append(video.path)
            self._rel_paths_by_row.append(video.rel_path)
            if video.path == previous_path:
                restore_row = len(self._paths_by_row) - 1
        # setCurrentRow() while still inside the block -- clear() resets
        # the widget's current row to -1, so calling it *after*
        # blockSignals(False) fired currentRowChanged (a real transition
        # from -1) on every single set_videos() call, even when the
        # "restored" row is the exact video that was already selected.
        # MainWindow's video_selected handler reloads the video
        # unconditionally, so this was resetting playback to 0 and
        # briefly stalling on ffprobe/mpv reopening the file every time
        # refresh_playlist() ran -- which fires on nearly every mutating
        # action (Mark Annotated, Add Annotation, ...), not just on
        # project open or an actual video switch. Reported as a real bug.
        if restore_row >= 0:
            self._list.setCurrentRow(restore_row)
        elif self._paths_by_row:
            self._list.setCurrentRow(0)
        self._list.blockSignals(False)
        # Only notify if the selection actually changed (a different video
        # is current now than before this refresh, e.g. first-ever
        # population, or the previously-selected video no longer exists).
        new_path = self.current_path()
        if new_path is not None and new_path != previous_path:
            self.video_selected.emit(new_path)

    def set_thumbnail(self, rel_path: str, thumbnail_path: str) -> None:
        """Set a single row's icon in place, without rebuilding the list --
        thumbnails now arrive asynchronously, one at a time, well after
        set_videos() already ran (ThumbnailLoader); rebuilding the whole
        list per arrival would re-fire currentRowChanged (reloading the
        selected video) for no reason on every single thumbnail.
        """
        if rel_path not in self._rel_paths_by_row:
            return
        row = self._rel_paths_by_row.index(rel_path)
        self._list.item(row).setIcon(QIcon(thumbnail_path))

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

    def previous_path(self) -> str | None:
        row = self._list.currentRow()
        if 0 <= row - 1 < len(self._paths_by_row):
            return self._paths_by_row[row - 1]
        return None

    def select_path(self, path: str) -> None:
        if path in self._paths_by_row:
            self._list.setCurrentRow(self._paths_by_row.index(path))

    def select_relative(self, delta: int) -> None:
        """Move the selection by `delta` rows (e.g. -1/+1 for prev/next
        video), clamped to the list's bounds. No-op past either end.
        """
        if not self._paths_by_row:
            return
        row = self._list.currentRow()
        new_row = min(max(row + delta, 0), len(self._paths_by_row) - 1)
        if new_row != row:
            self._list.setCurrentRow(new_row)

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._paths_by_row):
            self.video_selected.emit(self._paths_by_row[row])
