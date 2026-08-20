# CLAUDE.md

Instructions and durable context for Claude Code (or any other agent) working
in this repository. Read this before making changes. See also
`REQUIREMENT.md` (the spec this tool implements), `CHANGELOG.md` (what
changed and when), and `BACKLOG.md` (what's intentionally not done yet).

## What this is

A macOS desktop tool for annotating videos with **cuts** (start/end time +
label) without ever modifying the source video files. It only writes
annotation mapping files. See `REQUIREMENT.md` for the full functional and
non-functional spec — treat that file as the source of truth for behavior;
this file is about how the codebase is organized and how to work in it.

## Tech stack (chosen deliberately, don't swap without asking)

- **Python 3.11+**, packaged as `src/vat` (import name `vat`, CLI command
  `vat`, entry point `vat.app:main`).
- **PySide6** (Qt6) for the UI.
- **python-mpv** (wrapping Homebrew's `libmpv`) for video playback, embedded
  into a `QWidget` via `winId()`. Chosen over `QtMultimedia`/`Electron`
  specifically for low RAM/CPU footprint and hardware-accelerated decode —
  see the non-functional requirements in `REQUIREMENT.md` (<4GB RAM, "use
  pre-existing tools", DaVinci-Resolve-like feel).
- `ffprobe` (from the `ffmpeg` Homebrew formula) for video duration probing.
- System deps expected to already be installed via Homebrew: `brew install
  mpv ffmpeg`.

## Known environment issue: libmpv on macOS Tahoe (READ THIS)

On this machine (macOS Tahoe 26.2, Apple Silicon), the system
`OpenGL.framework` no longer exports the `_CGLGetCurrentContext` symbol that
Homebrew's `libmpv` still references from an unused legacy Cocoa/OpenGL code
path (mpv's actual renderer is Vulkan/libplacebo now). `ctypes.CDLL` opens
libraries with eager symbol resolution and fails outright on that missing
symbol — **even though running the `mpv` CLI binary directly works fine**,
because normal process loading binds that particular unused symbol lazily
and never actually resolves it.

This is fixed in `src/vat/playback/_mpv_bootstrap.py`, which must be
imported before `import mpv` anywhere (it already is, at the top of
`src/vat/playback/mpv_player.py`). It pre-loads `libmpv.dylib` itself with
`RTLD_LAZY` so python-mpv's own `CDLL(sofile)` call just bumps the refcount
on an already-successfully-loaded image instead of re-triggering eager
resolution. It also works around `ctypes.util.find_library('mpv')`
returning `None` for Homebrew libs outside the default dyld search path.

**If you ever see `OSError: ... Symbol not found: _CGLGetCurrentContext`**,
this is why. Don't try to "fix" it by downgrading/reinstalling mpv — it's
reproducible against the current Homebrew bottle (0.41.0_8) and is an OS/lib
interaction, not a version mismatch. If a future macOS or mpv release fixes
the root cause, `_mpv_bootstrap.ensure_libmpv_loadable()` becomes a no-op
automatically (it first checks whether `find_library` already succeeds).

There is a second, separate landmine in the same area: **`QApplication`
resets `LC_NUMERIC` away from `"C"`** during its own init, undoing the fix
python-mpv applies at `import mpv` time. libmpv hard-aborts the whole
process (prints `Non-C locale detected. This is not supported.` to stderr
and exits — not a catchable Python exception) if `LC_NUMERIC` isn't `"C"`
when an `MPV()` instance is actually created. Reproduced this for real: the
app launched fine under `QT_QPA_PLATFORM=offscreen` pytest runs (no
`QApplication`-driven locale reset had bitten yet because tests never
construct a real `MpvPlayer`), but hard-crashed on first real run once a
video was loaded. Fixed by re-asserting
`locale.setlocale(locale.LC_NUMERIC, "C")` at the top of
`MpvPlayer.__init__` (`src/vat/playback/mpv_player.py`), right before
`mpv.MPV(...)` is constructed, rather than relying on import-time ordering.

## Architecture

```
src/vat/
  models/        Plain dataclasses: Label, Cut, VideoEntry, ProjectConfig.
                 JSON round-trippable (to_dict/from_dict), no I/O.
  project/       project_store.py: reads/writes the private project.json
                 (videos_dir, project_dir, labels). project.py: Project
                 facade combining project_store + annotation_store so
                 operations spanning both (label rename) stay in sync.
  annotations/   annotation_store.py: reads/writes the public
                 annotations.json (video path -> {annotated, cuts[]}).
  media/         video_scanner.py: flat playlist listing of a videos dir
                 + ffprobe duration probing (in-process cached).
  playback/      mpv_player.py (+ _mpv_bootstrap.py) and preloader.py.
  ui/            PySide6 widgets. MainWindow is the controller; every other
                 panel (playlist_panel, video_panel, timeline_widget,
                 inspector_panel) is a "dumb" widget that only emits Qt
                 signals and exposes setters -- it does not touch Project
                 or annotation_store directly. Keep it this way: it's what
                 makes the controller logic testable without a display
                 driving real video playback.
  app.py         QApplication bootstrap / entry point.
  app_settings.py  Tiny ~/Library/Application Support/vat/settings.json
                 for remembering the last-opened project across launches.
```

### Two files per project, on purpose

- `project.json` (private): videos_dir, project_dir, the label set
  (name + shortcut), timestamps. Internal app config.
- `annotations.json` (**public**, per REQUIREMENT.md #7): video path ->
  `{annotated: bool, cuts: [{id, start, end, label}]}`. Cuts store the
  **label name as a plain string**, not a foreign key into project.json's
  label list. This is deliberate: the annotations file must be readable and
  meaningful entirely on its own. The tradeoff is that renaming a label
  requires rewriting every matching cut across the whole annotations file --
  `Project.rename_label()` does this atomically via
  `AnnotationStore.rename_label_everywhere()`. Don't switch to id-based
  label references without revisiting this requirement.

### The "annotated" flag is not just "has cuts"

Per `REQUIREMENT.md`'s Definitions section: a video is annotated only once
there's an entry for it (created either by adding a cut, or by an explicit
user confirmation for an intentionally-empty video) **and** the user has
explicitly pressed "mark annotated". Adding cuts alone does not flip
`annotated` to `True` — that requires the explicit confirm action. Both
`AnnotationStore` and the test suite encode this distinction; preserve it.

## Branches

- `main` is the development branch (default; everything lands here first).
- `prod` is the "deployment" branch — for this project, deployment means the
  user running the app locally on their own Mac. Merge `main` into `prod`
  (fast-forward when possible) only for versions considered
  stable/run-worthy, not on every commit.

## Running things

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/vat                 # or: .venv/bin/python -m vat
.venv/bin/pytest               # QT_QPA_PLATFORM=offscreen is set in tests/conftest.py
```

## Testing conventions

- Tests run with `QT_QPA_PLATFORM=offscreen` (set globally in
  `tests/conftest.py`) so the suite is headless-safe.
- **Never let a test cause a real video to be selected through
  `PlaylistPanel`/`MainWindow.refresh_playlist()`** when the videos
  directory is non-empty at `MainWindow` construction time. Row-0
  auto-selection fires `_on_video_selected`, which constructs a real
  `MpvPlayer` (real `libmpv`) and embeds it into the window's `winId()` --
  under the offscreen platform this **segfaults the whole test process**
  (reproduced once; see git history / CHANGELOG). UI controller tests use an
  *empty* videos directory and poke `MainWindow._current_video_path`
  directly instead. This is not a hypothetical risk — keep new UI tests
  consistent with `tests/test_ui_controller.py`.
- Core logic (models, project_store, annotation_store, video_scanner,
  Project facade) has no Qt/mpv dependency and is straightforward to test
  directly — prefer adding coverage there over UI-level tests.

## Process expectations for this repo

- Keep `CHANGELOG.md` updated (Keep a Changelog style) for user-visible
  changes.
- Keep `BACKLOG.md` updated with anything intentionally deferred or
  discovered-but-not-done, so it doesn't get silently lost.
- Commit incrementally with descriptive messages as work lands, rather than
  batching unrelated changes into one commit.
