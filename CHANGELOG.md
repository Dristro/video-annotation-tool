# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added: edit existing annotations (REQUIREMENT.md #10)

- A cut can now be edited after the fact, not just deleted and re-added --
  in particular, one flagged incomplete (missing a score added after it
  was created) can now actually be fixed instead of just showing a
  warning forever.
- Selecting a cut -- by clicking it on the timeline/progress bar, or in
  the Cuts list -- loads its current label and scores into the same
  fields used to add a new annotation: existing values show up prefilled,
  any score the cut doesn't have yet is left blank. A new "Edit
  Annotation" button (next to "Add Annotation", to its left/inside per
  request) saves the change back onto that same cut.
- "Edit Annotation" only enables once every current score field is valid
  -- same requirement as "Add Annotation" -- specifically to prevent an
  edit from silently wiping out a previously-recorded score the user
  didn't intend to touch (`AnnotationStore.update_cut(scores=...)`
  replaces the whole scores dict when given one).
- Removed the standalone "Edit Scores…" button from the inspector panel
  -- scoring configuration is now reached only via **Edit > Edit
  Scores…**, keeping this panel focused on the current annotation.
- `ScoreDefinition` gained a `description` field (free text describing
  what the score means), shown in the score editor's table and as a
  tooltip on the score's input field. Threaded through
  `project_store`/`Project` CRUD and `ScoreEditorDialog`'s add/edit form.
- 7 new tests (94 total).

### Added: per-cut scores (REQUIREMENT.md #9)

- New optional, per-project feature: alongside a cut's label, the user can
  now record one or more named numeric scores. Off by default; toggled
  per project in **Edit > Edit Scores…**.
- Each score has its own independent name, range (min/max), and dtype
  (float or int) -- new score fields default to 0-100/float, both editable
  per score. `ScoreEditorDialog` manages the set (add/remove/rename,
  mirroring `LabelEditorDialog`); renaming a score propagates into every
  cut that already recorded a value under the old name
  (`AnnotationStore.rename_score_everywhere`).
- When scoring is enabled, the right-hand panel's "New Cut" group is now
  "New Annotation": every currently-defined score becomes a required,
  genuinely blank input (no pre-filled value) next to the label picker.
  Out-of-range or wrong-dtype values are rejected outright (validated via
  `ScoreDefinition.coerce()`); "Add Annotation" stays disabled with an
  inline error until every field is valid.
- A score added to project settings after cuts already exist is **not**
  retroactively required -- existing cuts simply don't have that key.
  `Project.is_cut_complete()`/`.missing_scores()` compute this on the fly,
  and the cuts list shows a "⚠ missing: ..." marker for affected cuts, per
  the user's explicit choice to flag rather than block or silently accept.
- `Cut` gained a `scores: dict[str, float]` field; `ProjectConfig` gained
  `scoring_enabled` and `score_definitions`. New model:
  `models/score_definition.py`.
- 42 new tests (87 total) covering `ScoreDefinition` validation/coercion,
  the full CRUD + rename-propagation path through `project_store` and the
  `Project` facade, `annotation_store.rename_score_everywhere`, and the
  InspectorPanel validation/incomplete-flagging flow through
  `MainWindow`.

### Changed (reported: video still opened in a separate window after the
previous fix; close button didn't work, had to force-quit)

- Replaced `wid`-based window embedding with mpv's client **Render API**
  for video playback -- a structural change, not another timing tweak.
  `wid` embedding (handing mpv a native window/view to manage) had failed
  across two separate real fix attempts (wrong `vo`, then a `winId()`
  timing issue) -- the video kept opening in its own separate OS window,
  and closing the app hung indefinitely. mpv's macOS video output has only
  limited support for embedding into a foreign NSView. The Render API
  sidesteps this whole class of problem: mpv never owns or touches any
  window -- `VideoSurface` (now a `QOpenGLWidget`) owns the OpenGL context
  and framebuffer, and mpv just renders frames into it via
  `mpv.MpvRenderContext`. Along the way, fixed a real crash from not
  explicitly wrapping the `get_proc_address` callback in mpv's ctypes
  `CFUNCTYPE` (`TypeError: expected CFunctionType instance, got
  function`). Full writeup in `CLAUDE.md` ("Video rendering architecture").
- `MpvPlayer` no longer takes a `surface` argument; it just owns mpv's
  core client instance (`.core` property). `VideoSurface.bind_player()` /
  `.release_player()` manage the render context's lifecycle separately.

### Fixed (video played in a separate OS window; slider only seeked on
release, not while dragging)

- Video opened in its own separate window instead of embedding into the
  main tool window. Root cause: `MainWindow.__init__` called
  `refresh_playlist()` synchronously, which can auto-select the first
  video and load it -- constructing a real `MpvPlayer`, which calls
  `surface.winId()` to hand mpv a native window to embed into. This ran
  *before* `app.py` calls `window.show()`, so the widget had never been
  part of an on-screen window hierarchy yet; mpv fell back to opening its
  own top-level window instead of embedding into ours. Fixed by deferring
  that first `refresh_playlist()` call via `QTimer.singleShot(0, ...)`,
  which only fires once the Qt event loop actually starts running (i.e.
  after `.show()` has already executed).
- Scrubbing the position slider only sought once the mouse was released.
  Added a `sliderMoved` connection (fires continuously during a drag,
  unlike `valueChanged`) that seeks live as the slider moves, so scrubbing
  now updates the video in real time.

### Fixed (reported from a real run on the `prod` branch)

- **Video didn't render** (audio/scrubbing worked, frame stayed blank):
  `MpvPlayer` was passing `vo="libmpv"`, which is the driver for mpv's
  *render API* (rendering into an offscreen FBO you manage yourself), not
  for `wid`-based window embedding. Removed it so mpv falls back to its
  default `gpu`/libplacebo VO, which is what actually draws into an
  embedded window.
- Removed `WA_PaintOnScreen` from `VideoSurface` — Qt's docs call this
  attribute unsupported on macOS's Cocoa backend; it was producing the
  repeating `QWidget::paintEngine: Should no longer be called` warning and
  fighting mpv's native rendering.
- Fixed a `modalSession has been exited prematurely` Cocoa warning caused
  by `ProjectDialog` staying visible+modal underneath `NewProjectDialog`
  while the latter opened native folder pickers (three stacked modal
  sessions). `ProjectDialog` now hides itself while `NewProjectDialog` is
  up.

### Fixed (reported: app opens but the cursor spins forever / never
finishes loading)

- Root-caused via `sample <pid>` thread dumps to a genuine deadlock:
  `VideoPanel` polled `MpvPlayer.position`/`.duration` (synchronous
  `mpv_get_property` calls) from a `QTimer` on the Qt main thread every
  200ms. On macOS, mpv's video output does a `dispatch_sync` onto the
  **main queue** during Cocoa/Metal setup shortly after `load()`, and
  mpv's core thread won't service *any* other request (including property
  reads) until that finishes. If the main thread is blocked inside one of
  our polled property reads at that moment, it can never return to pump
  Cocoa's run loop, which is the only thing that can unblock mpv's
  main-queue dispatch -- so nothing ever proceeds. A 200ms timer firing
  right after `load()` hit this every single time.
  Fixed by replacing the polling entirely with mpv's async property
  observers (`observe_position`/`observe_duration`/`observe_pause`, which
  deliver on mpv's own event thread) feeding into Qt signals, which are
  thread-safe to `.emit()` from any thread and get auto-queued onto the
  main thread for the actual widget updates. See `CLAUDE.md` for the full
  writeup.

### Added

- Project scaffolding: `src/vat` package, `pyproject.toml` (PySide6 +
  python-mpv), venv-based dev workflow.
- Core data layer: `Label`, `Cut`, `VideoEntry`, `ProjectConfig` models.
- `project_store`: create/load the private `project.json`, label CRUD, and
  moving the whole project directory to a new location.
- `annotation_store`: create/load the public `annotations.json` mapping
  video path -> `{annotated, cuts[]}`, matching the spec's precise
  definition of "annotated".
- `Project` facade tying config + annotations together, in particular
  propagating label renames into every existing cut in the annotations
  file.
- `media.video_scanner`: flat playlist listing of a videos directory plus
  `ffprobe`-based duration probing.
- Playback layer: `MpvPlayer`/`VideoSurface` (libmpv embedded in a
  `QWidget`, bounded demuxer cache to respect the RAM budget) and
  `Preloader` (background warm-up of the next playlist video's head bytes +
  duration).
- Full PySide6 UI, DaVinci-Resolve-like layout: `PlaylistPanel`,
  `VideoPanel`, `TimelineWidget`, `InspectorPanel`, `LabelEditorDialog`,
  `ProjectDialog`/`NewProjectDialog`, wired together by `MainWindow`.
  Keyboard shortcuts: space (play/pause), I/O (mark in/out), left/right
  (seek), and per-label custom shortcut keys (editable at runtime).
- App-level "remember last opened project" via `~/Library/Application
  Support/vat/settings.json`.
- pytest suite (45 tests) covering models, project_store, annotation_store,
  the Project facade, video_scanner, and MainWindow's controller glue.
- `Label` gained a `description` field. Label shortcuts are now full key
  sequences (e.g. `Ctrl+Shift+G`), captured via `QKeySequenceEdit`, not a
  single character. The label editor is now a table (index / name /
  description / shortcut) instead of a plain list, per user feedback.

### Fixed

- Worked around a macOS Tahoe (26.2) libmpv loading failure
  (`_CGLGetCurrentContext` missing from the system `OpenGL.framework`,
  which Homebrew's libmpv still references from an unused legacy code
  path) via `playback/_mpv_bootstrap.py`. See `CLAUDE.md` for the full
  explanation.
- Fixed a real-launch-only crash (not caught by the offscreen pytest
  suite) where `QApplication` resets `LC_NUMERIC` after python-mpv's
  import-time fix, causing libmpv to hard-abort the process on the first
  video load. Fixed in `MpvPlayer.__init__`; see `CLAUDE.md`.

### Known issues / deferred

- See `BACKLOG.md`.
