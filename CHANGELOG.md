# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

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
- pytest suite (42 tests) covering models, project_store, annotation_store,
  the Project facade, video_scanner, and MainWindow's controller glue.

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
