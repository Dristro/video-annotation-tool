from __future__ import annotations

import os
import uuid

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QSplitter, QVBoxLayout, QWidget

from vat import app_settings
from vat.constants import THUMBNAILS_DIR_NAME, WAVEFORMS_DIR_NAME
from vat.errors import CutNotFoundError
from vat.media.video_scanner import probe_duration
from vat.playback.preloader import Preloader
from vat.playback.thumbnail_loader import ThumbnailLoader
from vat.playback.waveform_loader import WaveformLoader
from vat.project.project import Project
from vat.project.undo_stack import Command, UndoStack
from vat.ui.inspector_panel import InspectorPanel
from vat.ui.playlist_panel import PlaylistPanel
from vat.ui.project_settings_dialog import ProjectSettingsDialog
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
        self._waveform_loader = WaveformLoader()
        self._waveform_loader.loaded.connect(self._on_waveform_loaded)
        self._thumbnail_loader = ThumbnailLoader()
        self._thumbnail_loader.loaded.connect(self._on_thumbnail_loaded)
        # Covers cut add/edit/delete only, not label/score renames --
        # those propagate across every video's cuts (rename_*_everywhere)
        # and would need a full before/after snapshot of every affected
        # cut to undo cleanly, which is meaningfully more machinery than
        # this stack currently has (BACKLOG.md).
        self._undo_stack = UndoStack()

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

        self._recent_menu = file_menu.addMenu("Open Recent")
        self._refresh_recent_menu()

        file_menu.addSeparator()

        change_videos_action = file_menu.addAction("Change Videos Directory…")
        change_videos_action.triggered.connect(self._on_change_videos_dir)

        change_project_dir_action = file_menu.addAction("Change Project Directory…")
        change_project_dir_action.triggered.connect(self._on_change_project_dir)

        file_menu.addSeparator()
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)

        edit_menu = self.menuBar().addMenu("&Edit")
        undo_action = edit_menu.addAction("Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self._on_undo)
        redo_action = edit_menu.addAction("Redo")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self._on_redo)
        edit_menu.addSeparator()
        project_settings_action = edit_menu.addAction("Project Settings…")
        project_settings_action.triggered.connect(self._on_open_project_settings)

    # -- Signal wiring ------------------------------------------------------------
    def _wire_signals(self) -> None:
        self.playlist_panel.video_selected.connect(self._on_video_selected)
        self.playlist_panel.change_videos_dir_requested.connect(self._on_change_videos_dir)

        self.video_panel.position_changed.connect(self.timeline_widget.set_position)
        self.video_panel.duration_changed.connect(self.timeline_widget.set_duration)

        self.timeline_widget.seek_requested.connect(self.video_panel.seek_to)
        self.timeline_widget.cut_selected.connect(self.inspector_panel.select_cut_by_id)
        self.timeline_widget.cut_double_clicked.connect(self._on_timeline_cut_double_clicked)
        self.timeline_widget.cut_resized.connect(self._on_cut_resized)

        self.inspector_panel.mark_in_requested.connect(self._on_mark_in)
        self.inspector_panel.mark_out_requested.connect(self._on_mark_out)
        self.inspector_panel.add_cut_requested.connect(self._on_add_cut)
        self.inspector_panel.edit_cut_requested.connect(self._on_edit_cut)
        self.inspector_panel.delete_cut_requested.connect(self._on_delete_cut)
        self.inspector_panel.break_continuation_requested.connect(self._on_break_continuation)
        self.inspector_panel.seek_to_cut_requested.connect(self._on_seek_to_cut)
        self.inspector_panel.set_annotated_requested.connect(self._on_set_annotated)
        self.inspector_panel.edit_labels_requested.connect(lambda: self._on_open_project_settings("labels"))
        self.inspector_panel.navigate_requested.connect(self._on_navigate_requested)

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self.video_panel.toggle_pause)
        QShortcut(QKeySequence(Qt.Key.Key_I), self, activated=self._on_mark_in)
        QShortcut(QKeySequence(Qt.Key.Key_O), self, activated=self._on_mark_out)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=lambda: self._on_navigate_requested("left"))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=lambda: self._on_navigate_requested("right"))
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, activated=lambda: self._on_navigate_requested("up"))
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, activated=lambda: self._on_navigate_requested("down"))

    def _on_navigate_requested(self, direction: str) -> None:
        """Left/Right seek, Up/Down step through the playlist. Shared by
        the global shortcuts and by score fields' arrow keys (see
        TransportLineEdit) -- score fields would otherwise swallow plain
        arrow keys for in-field cursor movement, which was reported as a
        real bug (transport controls going dead once a score field had
        focus).
        """
        if direction == "left":
            self.video_panel.seek_relative(-SEEK_STEP_SECONDS)
        elif direction == "right":
            self.video_panel.seek_relative(SEEK_STEP_SECONDS)
        elif direction == "up":
            self.playlist_panel.select_relative(-1)
        elif direction == "down":
            self.playlist_panel.select_relative(1)

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
        cut_counts = {}
        for v in videos:
            entry = self.project.get_entry(v.rel_path)
            if entry:
                cut_counts[v.rel_path] = len(entry.cuts)
        # No thumbnails passed here -- ThumbnailLoader fills them in
        # asynchronously via set_thumbnail() below (per row, as each one
        # arrives) rather than this blocking on ffmpeg for any video that
        # isn't already cached. refresh_playlist() fires on nearly every
        # mutating action (add/edit/delete a cut, mark annotated, ...),
        # not just project open, so it must never itself do slow work --
        # doing thumbnail extraction inline here used to hang the UI for
        # several seconds on "Mark Annotated" (reported as a real bug),
        # worse yet on every retry if a video's thumbnail extraction kept
        # failing (no cache file ever got written, so it retried every
        # single call).
        self.playlist_panel.set_videos(videos, annotated_flags, cut_counts)
        thumbnails_dir = os.path.join(self.project.config.project_dir, THUMBNAILS_DIR_NAME)
        self._thumbnail_loader.load_missing(videos, thumbnails_dir)

    def _on_thumbnail_loaded(self, rel_path: str, thumbnail_path: str) -> None:
        if thumbnail_path:
            self.playlist_panel.set_thumbnail(rel_path, thumbnail_path)

    def _on_video_selected(self, path: str) -> None:
        self._current_video_path = path
        rel = self.project.rel_path(path)
        self.video_panel.load(path)
        self.inspector_panel.set_video_name(rel)
        self.inspector_panel.clear_pending()
        self._refresh_cuts_and_status(rel)
        self._refresh_pending_continuation()

        duration = probe_duration(path)
        if duration:
            self.timeline_widget.set_duration(duration)

        # Clear immediately rather than leaving the previous video's
        # waveform showing while the new one decodes in the background --
        # set_waveform(None) also correctly re-draws an empty strip if
        # this video's waveform was never generated at all.
        self.timeline_widget.set_waveform(None)
        waveforms_dir = os.path.join(self.project.config.project_dir, WAVEFORMS_DIR_NAME)
        self._waveform_loader.load(path, waveforms_dir)

        next_path = self.playlist_panel.next_path()
        if next_path:
            self._preloader.preload(next_path)

    def _on_waveform_loaded(self, video_path: str, peaks: list) -> None:
        # Guards against a late result for a video the user has already
        # navigated away from overwriting the *current* video's waveform.
        if video_path == self._current_video_path:
            self.timeline_widget.set_waveform(peaks or None)

    def _refresh_pending_continuation(self) -> None:
        """Check whether the previous video (by playlist order) left an
        annotation continuing into the current one still uncompleted, and
        tell the inspector to show/hide its "Start Here" banner
        accordingly. Also disables the "continues into next video"
        checkbox when there's no next video to continue into.
        """
        if self._current_video_path is None:
            self.inspector_panel.set_pending_continuations([])
            return
        rel = self.project.rel_path(self._current_video_path)
        previous_path = self.playlist_panel.previous_path()
        previous_rel = self.project.rel_path(previous_path) if previous_path else None
        pending = self.project.pending_continuations(rel, previous_rel)
        self.inspector_panel.set_pending_continuations(pending)
        self.inspector_panel.set_continuation_allowed(self.playlist_panel.next_path() is not None)

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
        continues_forward = self.inspector_panel.wants_continues_forward()
        # A continuing cut's true end isn't something the user marks --
        # it's however far this video actually runs; Mark Out is ignored
        # (and not even required, see InspectorPanel._refresh_button_states)
        # when the checkbox is checked.
        end = self.video_panel.duration() if continues_forward else self.inspector_panel.pending_out()
        if start is None or end is None or end <= start:
            return
        if self.project.overlapping_cuts(rel, start, end):
            # Allowed, not blocked (REQUIREMENT.md doesn't forbid it) --
            # just a heads-up in case it wasn't intentional.
            confirm = QMessageBox.question(
                self,
                "Overlapping Annotation",
                "This overlaps an existing annotation on this video. Add it anyway?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        scores = self.inspector_panel.pending_scores()
        # completing_continuation_id() is set when this Add Annotation is
        # finishing the back half of a continuation started in the
        # previous video (via the "Start Here" banner). If continues_forward
        # is *also* checked, this same cut continues further into the video
        # after this one -- reuse the same id rather than minting a new one:
        # pending_continuation() only ever checks one hop of adjacency at a
        # time, so propagating a single shared id through every cut in a
        # 3+-video chain still links each adjacent pair correctly, and a
        # fresh id here would silently sever the chain at this cut instead.
        # A fresh id is only needed when this cut isn't completing anything
        # (the start of a new chain).
        continuation_id = self.inspector_panel.completing_continuation_id()
        if continues_forward and continuation_id is None:
            continuation_id = uuid.uuid4().hex
        new_cut = self.project.add_cut(
            rel, start, end, label, scores,
            continuation_id=continuation_id, continues_forward=continues_forward,
        )
        self._undo_stack.push(Command(
            undo=lambda: self._remove_cut_and_sync(rel, new_cut.id),
            redo=lambda: self._restore_cut_and_sync(rel, new_cut),
        ))
        self.inspector_panel.clear_pending()
        self._refresh_cuts_and_status(rel)
        self.refresh_playlist()  # annotation count for this video just changed
        self._refresh_pending_continuation()  # this add may have just completed one

    def _remove_cut_and_sync(self, rel: str, cut_id: str) -> None:
        try:
            self.project.remove_cut(rel, cut_id)
        except CutNotFoundError:
            pass
        self._sync_after_undo_redo(rel)

    def _restore_cut_and_sync(self, rel: str, cut) -> None:
        self.project.restore_cut(rel, cut)
        self._sync_after_undo_redo(rel)

    def _on_edit_cut(self, label: str) -> None:
        if self._current_video_path is None:
            return
        cut_id = self.inspector_panel.selected_cut_id()
        if cut_id is None:
            return
        rel = self.project.rel_path(self._current_video_path)
        entry = self.project.get_entry(rel)
        old_cut = next((c for c in entry.cuts if c.id == cut_id), None) if entry else None
        if old_cut is None:
            return
        scores = self.inspector_panel.pending_scores()
        retime = self.inspector_panel.pending_retime()
        new_start, new_end = retime if retime is not None else (old_cut.start, old_cut.end)
        if retime is not None:
            if self.project.overlapping_cuts(rel, new_start, new_end, exclude_cut_id=cut_id):
                confirm = QMessageBox.question(
                    self,
                    "Overlapping Annotation",
                    "This new range overlaps an existing annotation on this video. Save it anyway?",
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return
        self._apply_cut_snapshot(rel, cut_id, new_start, new_end, label, scores)
        self._undo_stack.push(Command(
            undo=lambda: self._apply_cut_snapshot(
                rel, cut_id, old_cut.start, old_cut.end, old_cut.label, old_cut.scores
            ),
            redo=lambda: self._apply_cut_snapshot(rel, cut_id, new_start, new_end, label, scores),
        ))

    def _apply_cut_snapshot(
        self, rel: str, cut_id: str, start: float, end: float, label: str, scores: dict,
    ) -> None:
        """Overwrite a cut's start/end/label/scores in one shot -- shared
        by _on_edit_cut and its undo/redo commands, since both are "make
        this cut look like this snapshot" with no partial-field semantics.
        """
        self.project.update_cut(rel, cut_id, start=start, end=end, label=label, scores=dict(scores))
        if self._current_video_path and self.project.rel_path(self._current_video_path) == rel:
            self._refresh_cuts_and_status(rel)
            # Re-select the same cut so the panel visibly reflects the
            # saved values rather than losing selection when the list
            # rebuilds.
            self.inspector_panel.select_cut_by_id(cut_id)

    def _on_cut_resized(self, cut_id: str, start: float, end: float) -> None:
        """TimelineWidget's edge-drag already enforces a minimum length
        live, so `start < end` should always hold here -- checked anyway
        since this is data arriving from a signal, not a direct call.
        """
        if self._current_video_path is None or end <= start:
            return
        rel = self.project.rel_path(self._current_video_path)
        entry = self.project.get_entry(rel)
        old_cut = next((c for c in entry.cuts if c.id == cut_id), None) if entry else None
        if old_cut is None:
            return
        if (start, end) == (old_cut.start, old_cut.end):
            return  # e.g. a click that grabbed an edge but didn't actually move it
        if self.project.overlapping_cuts(rel, start, end, exclude_cut_id=cut_id):
            confirm = QMessageBox.question(
                self,
                "Overlapping Annotation",
                "This new range overlaps an existing annotation on this video. Save it anyway?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                self._refresh_cuts_and_status(rel)  # repaint the timeline back to the committed range
                return
        self._apply_cut_snapshot(rel, cut_id, start, end, old_cut.label, old_cut.scores)
        self._undo_stack.push(Command(
            undo=lambda: self._apply_cut_snapshot(
                rel, cut_id, old_cut.start, old_cut.end, old_cut.label, old_cut.scores
            ),
            redo=lambda: self._apply_cut_snapshot(rel, cut_id, start, end, old_cut.label, old_cut.scores),
        ))

    def _on_delete_cut(self, cut_id: str) -> None:
        if self._current_video_path is None:
            return
        rel = self.project.rel_path(self._current_video_path)
        entry = self.project.get_entry(rel)
        old_cut = next((c for c in entry.cuts if c.id == cut_id), None) if entry else None
        try:
            self.project.remove_cut(rel, cut_id)
        except CutNotFoundError:
            return
        if old_cut is not None:
            self._undo_stack.push(Command(
                undo=lambda: self._restore_cut_and_sync(rel, old_cut),
                redo=lambda: self._remove_cut_and_sync(rel, cut_id),
            ))
        self._refresh_cuts_and_status(rel)
        self.refresh_playlist()  # annotation count for this video just changed

    def _sync_after_undo_redo(self, rel: str) -> None:
        if self._current_video_path and self.project.rel_path(self._current_video_path) == rel:
            self._refresh_cuts_and_status(rel)
            self._refresh_pending_continuation()
        self.refresh_playlist()  # annotation count may have changed regardless of current video

    def _on_undo(self) -> None:
        self._undo_stack.undo()

    def _on_redo(self) -> None:
        self._undo_stack.redo()

    def _on_break_continuation(self, cut_id: str) -> None:
        if self._current_video_path is None:
            return
        rel = self.project.rel_path(self._current_video_path)
        confirm = QMessageBox.question(
            self,
            "Break Continuation Link",
            "Break this annotation's link to the cut it continues from/into? "
            "The other cut is left as-is (its own link becomes dangling, "
            "harmless, and can be broken separately).",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.project.break_continuation(rel, cut_id)
        self._refresh_cuts_and_status(rel)
        self.inspector_panel.select_cut_by_id(cut_id)
        # Breaking a front half's link removes the pending-continuation
        # banner the *next* video would otherwise show for it.
        self._refresh_pending_continuation()

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

    def _on_timeline_cut_double_clicked(self, cut_id: str) -> None:
        """Double-clicking a cut on the timeline both selects it (loading
        its label/scores into the inspector for editing) and seeks
        playback to its start, so the user can watch it while editing.
        """
        self.inspector_panel.select_cut_by_id(cut_id)
        self._on_seek_to_cut(cut_id)

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

    def _on_open_project_settings(self, initial_tab: str = "labels") -> None:
        dialog = ProjectSettingsDialog(self.project, self, initial_tab=initial_tab)
        dialog.exec()
        # Labels and scores are both on this one dialog now, so refresh
        # both regardless of which tab was opened -- either could have
        # been edited during the same session.
        self.inspector_panel.set_labels(self.project.config.labels)
        self.inspector_panel.set_score_definitions(
            self.project.config.scoring_enabled, self.project.config.score_definitions
        )
        self._register_label_shortcuts()
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

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        recents = [p for p in app_settings.load_recent_project_dirs() if p != self.project.config.project_dir]
        if not recents:
            empty_action = self._recent_menu.addAction("(No other recent projects)")
            empty_action.setEnabled(False)
            return
        for path in recents:
            action = self._recent_menu.addAction(path)
            action.triggered.connect(lambda checked=False, p=path: self._on_open_recent(p))

    def _on_open_recent(self, path: str) -> None:
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
        self._refresh_recent_menu()
        self._current_video_path = None
        self.refresh_playlist()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.video_panel.shutdown()
        super().closeEvent(event)
