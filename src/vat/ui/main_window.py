from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QSplitter, QVBoxLayout, QWidget

from vat import app_settings
from vat.errors import CutNotFoundError
from vat.media.video_scanner import probe_duration
from vat.playback.preloader import Preloader
from vat.project.project import Project
from vat.ui.inspector_panel import InspectorPanel
from vat.ui.label_editor_dialog import LabelEditorDialog
from vat.ui.playlist_panel import PlaylistPanel
from vat.ui.score_editor_dialog import ScoreEditorDialog
from vat.ui.timeline_widget import TimelineWidget
from vat.ui.video_panel import VideoPanel

SEEK_STEP_SECONDS = 5.0


class MainWindow(QMainWindow):
    """Top-level controller wiring the view panels to the Project facade.

    Layout mirrors DaVinci Resolve's arrangement: a playlist/media pool on
    the left, video preview + transport centered, a cut timeline beneath the
    preview, and an inspector for annotation actions on the right.
    """

    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self._current_video_path: str | None = None
        self._preloader = Preloader()

        self.setWindowTitle(f"Video Annotation Tool — {project.config.project_dir}")
        self.resize(1280, 800)

        self.playlist_panel = PlaylistPanel()
        self.video_panel = VideoPanel()
        self.timeline_widget = TimelineWidget()
        self.inspector_panel = InspectorPanel()

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(self.video_panel, stretch=1)
        center_layout.addWidget(self.timeline_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.playlist_panel)
        splitter.addWidget(center)
        splitter.addWidget(self.inspector_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        self.setCentralWidget(splitter)

        self._label_shortcuts: list[QShortcut] = []

        self._build_menu()
        self._wire_signals()
        self._install_shortcuts()

        self.inspector_panel.set_labels(self.project.config.labels)
        self.inspector_panel.set_score_definitions(
            self.project.config.scoring_enabled, self.project.config.score_definitions
        )
        self._register_label_shortcuts()

        # Deferred rather than called directly: refresh_playlist() can
        # auto-select the first video, which loads it into VideoPanel and
        # constructs a real MpvPlayer -- which calls surface.winId() to hand
        # mpv a native window to embed into. At this point in __init__, this
        # window has never been shown (app.py calls .show() only after
        # MainWindow() returns), so the native view mpv attaches to isn't
        # part of a real on-screen window hierarchy yet. Observed as a real
        # bug: mpv fell back to opening its own separate top-level window
        # instead of embedding into ours. QTimer.singleShot(0, ...) defers
        # this to the next event-loop iteration, which only happens once
        # app.exec() starts -- by then .show() has already run and the
        # window has a real native handle to embed into.
        QTimer.singleShot(0, self.refresh_playlist)

    # -- Menu ------------------------------------------------------------
    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        new_action = file_menu.addAction("New Project…")
        new_action.triggered.connect(self._on_new_project)

        open_action = file_menu.addAction("Open Project…")
        open_action.triggered.connect(self._on_open_project)

        file_menu.addSeparator()

        change_videos_action = file_menu.addAction("Change Videos Directory…")
        change_videos_action.triggered.connect(self._on_change_videos_dir)

        change_project_dir_action = file_menu.addAction("Change Project Directory…")
        change_project_dir_action.triggered.connect(self._on_change_project_dir)

        file_menu.addSeparator()
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_labels_action = edit_menu.addAction("Edit Labels…")
        edit_labels_action.triggered.connect(self._on_edit_labels)
        edit_scores_action = edit_menu.addAction("Edit Scores…")
        edit_scores_action.triggered.connect(self._on_edit_scores)

    # -- Signal wiring ------------------------------------------------------------
    def _wire_signals(self) -> None:
        self.playlist_panel.video_selected.connect(self._on_video_selected)
        self.playlist_panel.change_videos_dir_requested.connect(self._on_change_videos_dir)

        self.video_panel.position_changed.connect(self.timeline_widget.set_position)
        self.video_panel.duration_changed.connect(self.timeline_widget.set_duration)

        self.timeline_widget.seek_requested.connect(self.video_panel.seek_to)
        self.timeline_widget.cut_selected.connect(self.inspector_panel.select_cut_by_id)

        self.inspector_panel.mark_in_requested.connect(self._on_mark_in)
        self.inspector_panel.mark_out_requested.connect(self._on_mark_out)
        self.inspector_panel.add_cut_requested.connect(self._on_add_cut)
        self.inspector_panel.delete_cut_requested.connect(self._on_delete_cut)
        self.inspector_panel.seek_to_cut_requested.connect(self._on_seek_to_cut)
        self.inspector_panel.set_annotated_requested.connect(self._on_set_annotated)
        self.inspector_panel.edit_labels_requested.connect(self._on_edit_labels)
        self.inspector_panel.edit_scores_requested.connect(self._on_edit_scores)

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self.video_panel.toggle_pause)
        QShortcut(QKeySequence(Qt.Key.Key_I), self, activated=self._on_mark_in)
        QShortcut(QKeySequence(Qt.Key.Key_O), self, activated=self._on_mark_out)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=lambda: self.video_panel.seek_relative(-SEEK_STEP_SECONDS))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=lambda: self.video_panel.seek_relative(SEEK_STEP_SECONDS))

    def _register_label_shortcuts(self) -> None:
        """(Re)bind each label's custom shortcut key to select it in the inspector.

        Called on startup and after any label edit/rename/project switch, since
        the set of valid shortcuts can change at any time (REQUIREMENT.md: label
        shortcuts are editable after project creation).
        """
        for shortcut in self._label_shortcuts:
            shortcut.setParent(None)
        self._label_shortcuts.clear()
        for label in self.project.config.labels:
            if not label.shortcut:
                continue
            shortcut = QShortcut(QKeySequence(label.shortcut), self)
            shortcut.activated.connect(lambda name=label.name: self.inspector_panel.select_label(name))
            self._label_shortcuts.append(shortcut)

    # -- Playlist / video selection ------------------------------------------------------------
    def refresh_playlist(self) -> None:
        videos = self.project.list_videos()
        annotated_flags = {v.rel_path: self.project.is_annotated(v.rel_path) for v in videos}
        self.playlist_panel.set_videos(videos, annotated_flags)

    def _on_video_selected(self, path: str) -> None:
        self._current_video_path = path
        rel = self.project.rel_path(path)
        self.video_panel.load(path)
        self.inspector_panel.set_video_name(rel)
        self.inspector_panel.clear_pending()
        self._refresh_cuts_and_status(rel)

        duration = probe_duration(path)
        if duration:
            self.timeline_widget.set_duration(duration)

        next_path = self.playlist_panel.next_path()
        if next_path:
            self._preloader.preload(next_path)

    def _refresh_cuts_and_status(self, rel: str) -> None:
        entry = self.project.get_entry(rel)
        cuts = entry.cuts if entry else []
        self.timeline_widget.set_cuts(cuts)
        self.inspector_panel.set_cuts(
            cuts, self.project.config.score_definitions, self.project.config.scoring_enabled
        )
        self.inspector_panel.set_annotated(
            annotated=bool(entry and entry.annotated),
            has_entry=entry is not None,
        )

    # -- Mark in/out + cuts ------------------------------------------------------------
    def _on_mark_in(self) -> None:
        self.inspector_panel.set_pending_in(self.video_panel.position())

    def _on_mark_out(self) -> None:
        self.inspector_panel.set_pending_out(self.video_panel.position())

    def _on_add_cut(self, label: str) -> None:
        if self._current_video_path is None:
            return
        rel = self.project.rel_path(self._current_video_path)
        start = self.inspector_panel.pending_in()
        end = self.inspector_panel.pending_out()
        if start is None or end is None or end <= start:
            return
        scores = self.inspector_panel.pending_scores()
        self.project.add_cut(rel, start, end, label, scores)
        self.inspector_panel.clear_pending()
        self._refresh_cuts_and_status(rel)

    def _on_delete_cut(self, cut_id: str) -> None:
        if self._current_video_path is None:
            return
        rel = self.project.rel_path(self._current_video_path)
        try:
            self.project.remove_cut(rel, cut_id)
        except CutNotFoundError:
            return
        self._refresh_cuts_and_status(rel)

    def _on_seek_to_cut(self, cut_id: str) -> None:
        if self._current_video_path is None:
            return
        rel = self.project.rel_path(self._current_video_path)
        entry = self.project.get_entry(rel)
        if entry is None:
            return
        for cut in entry.cuts:
            if cut.id == cut_id:
                self.video_panel.seek_to(cut.start)
                return

    def _on_set_annotated(self, annotated: bool) -> None:
        if self._current_video_path is None:
            return
        rel = self.project.rel_path(self._current_video_path)
        self.project.set_annotated(rel, annotated)
        self._refresh_cuts_and_status(rel)
        self.refresh_playlist()
        self.playlist_panel.select_path(self._current_video_path)

    # -- Project-level actions ------------------------------------------------------------
    def _on_change_videos_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose Videos Directory", self.project.config.videos_dir)
        if path:
            self.project.set_videos_dir(path)
            self.refresh_playlist()

    def _on_change_project_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose New Project Directory")
        if not path:
            return
        try:
            self.project.move_project_dir(path)
        except Exception as exc:  # noqa: BLE001 -- surfaced directly to the user
            QMessageBox.warning(self, "Cannot Move Project", str(exc))
            return
        self.setWindowTitle(f"Video Annotation Tool — {self.project.config.project_dir}")
        app_settings.save_last_project_dir(self.project.config.project_dir)

    def _on_edit_labels(self) -> None:
        dialog = LabelEditorDialog(self.project, self)
        dialog.exec()
        self.inspector_panel.set_labels(self.project.config.labels)
        self._register_label_shortcuts()
        if self._current_video_path:
            self._refresh_cuts_and_status(self.project.rel_path(self._current_video_path))

    def _on_edit_scores(self) -> None:
        dialog = ScoreEditorDialog(self.project, self)
        dialog.exec()
        self.inspector_panel.set_score_definitions(
            self.project.config.scoring_enabled, self.project.config.score_definitions
        )
        if self._current_video_path:
            self._refresh_cuts_and_status(self.project.rel_path(self._current_video_path))

    def _on_new_project(self) -> None:
        from vat.ui.project_dialog import NewProjectDialog

        dialog = NewProjectDialog(self)
        if dialog.exec() and dialog.project is not None:
            self._switch_project(dialog.project)

    def _on_open_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose Project Directory")
        if not path:
            return
        try:
            project = Project.open(path)
        except Exception as exc:  # noqa: BLE001 -- surfaced directly to the user
            QMessageBox.warning(self, "Cannot Open Project", str(exc))
            return
        self._switch_project(project)

    def _switch_project(self, project: Project) -> None:
        self.project = project
        app_settings.save_last_project_dir(project.config.project_dir)
        self.setWindowTitle(f"Video Annotation Tool — {project.config.project_dir}")
        self.inspector_panel.set_labels(project.config.labels)
        self.inspector_panel.set_score_definitions(project.config.scoring_enabled, project.config.score_definitions)
        self._register_label_shortcuts()
        self._current_video_path = None
        self.refresh_playlist()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.video_panel.shutdown()
        super().closeEvent(event)
