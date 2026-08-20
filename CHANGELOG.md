# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

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
