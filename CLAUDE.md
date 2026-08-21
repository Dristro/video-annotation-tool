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
- **python-mpv** (wrapping Homebrew's `libmpv`) for video playback, rendered
  into a `QOpenGLWidget` via mpv's client Render API (see "Video rendering
  architecture" below — **not** `wid`-based window embedding, which was
  tried first and abandoned). Chosen over `QtMultimedia`/`Electron`
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

A fourth one, more serious than the others: **never call a synchronous mpv
property getter (`mpv_get_property`, e.g. python-mpv's `.time_pos` /
`.duration` / `.pause` properties) from the Qt main thread on a recurring
basis (a `QTimer`, in particular).** Confirmed this deadlocks 100% of the
time via `sample <pid>` thread dumps: shortly after `load()`, mpv's video
output does a `dispatch_sync` onto the **main queue** as part of its
Cocoa/Metal setup (`MacCommon.init`), and mpv's `core` thread blocks
(`mp_rendezvous`) waiting for that to finish before it'll service anything
else, including property reads. If the Qt main thread happens to be
blocked *inside* a synchronous `mpv_get_property` call at that exact
moment (which a 200ms polling timer firing immediately after `load()`
essentially guarantees), it can never return to pump Cocoa's run loop —
which is the only thing that can drain the main-queue dispatch mpv is
waiting on. Neither side can ever make progress. This produced exactly the
symptom reported: the app opens, but the beachball (spinning cursor) never
goes away.

The fix, in `MpvPlayer`/`VideoPanel`: there is no `position`/`duration`
synchronous getter anymore. Use `observe_position()` /
`observe_duration()` / `observe_pause()` instead — python-mpv delivers
these callbacks on its own background event thread (via `mpv_wait_event`,
a genuinely async mechanism, not the same lock path), and the callbacks do
nothing but `Signal.emit()` (thread-safe from any thread). The actual
widget updates happen in slots connected to those signals, which Qt
automatically queues onto the receiver's own thread (the main thread) when
the emit comes from a different thread — so no widget code ever runs
off-thread, and no code ever calls into mpv synchronously from a repeating
timer. `VideoPanel.position()`/`.duration()` return locally cached values
kept up to date by those observers, not live mpv reads. If you're tempted
to add a poll loop back in for anything mpv-related, don't — reproduce the
deadlock in your head first: does it call a synchronous mpv getter/setter
from the main thread more than once, without waiting on an async event in
between? If yes, it can hang exactly like this did.

## Video rendering architecture: Render API, not window embedding

**`VideoSurface` is a `QOpenGLWidget`, and mpv renders into it via the
client Render API (`mpv.MpvRenderContext`) -- mpv is never handed a native
window/view to manage itself.** This supersedes an earlier `wid`-based
approach (handing mpv a native window id via `surface.winId()` and letting
it embed/manage that window directly), which was tried across three
separate real fix attempts and never worked reliably on macOS:

1. First attempt used `vo="libmpv"` with `wid=...` together -- wrong:
   `vo=libmpv` is specifically the render-API driver name (only valid
   *without* `wid`); combined with `wid` it made mpv create its own
   context without ever drawing into the given window. (Also removed
   `WA_PaintOnScreen` from `VideoSurface` in this pass -- Qt's docs mark it
   unsupported on macOS/Cocoa, and it produced `QWidget::paintEngine:
   Should no longer be called` warning spam.)
2. Second attempt fixed the `vo` mistake and a timing bug (`winId()` was
   being forced before the top-level window had ever been shown, via
   `QTimer.singleShot(0, ...)` deferring the first `refresh_playlist()`
   call) -- **the video still opened in its own separate OS window, and
   closing the app hung indefinitely** (most likely mpv's Cocoa video
   output left in a partial/orphaned embedding state).

Two independent, structurally different fixes to the `wid` approach both
failed to actually embed the video. mpv's macOS video output has only
limited support for embedding into a foreign NSView -- well-known macOS mpv
frontends (e.g. IINA) don't rely on `--wid` embedding either. The Render
API sidesteps the whole class of Cocoa window-ownership problems: mpv
never creates or touches any window at all, it just writes decoded frames
into an OpenGL framebuffer that `VideoSurface` owns and controls,
inside `paintGL()`.

Mechanics, in `src/vat/playback/mpv_player.py`:

- `MpvPlayer` owns the core `mpv.MPV(vo="libmpv", ...)` client instance
  (no `wid`). `vo="libmpv"` is *required* here -- it tells mpv not to
  manage any window/view of its own, which is exactly what makes render-API
  embedding possible.
- `VideoSurface` (a `QOpenGLWidget`) is handed that core instance via
  `bind_player()`, but doesn't create the actual `MpvRenderContext` until
  `initializeGL()` fires (or immediately if a GL context already exists) --
  `mpv_render_context_create` requires a *current* OpenGL context on the
  calling thread, which only reliably exists inside/after Qt's own GL
  widget initialization, not whenever `bind_player()` happens to be called.
- The `get_proc_address` callback passed to mpv's OpenGL init params must
  be explicitly wrapped in `mpv.MpvGlGetProcAddressFn(...)` (a ctypes
  `CFUNCTYPE`) and that wrapped object kept alive as an instance attribute.
  Reproduced a real crash from skipping this (`TypeError: expected
  CFunctionType instance, got function`) -- assigning a plain Python
  function to a ctypes Structure field typed as a CFUNCTYPE doesn't
  auto-wrap the way passing one as an ordinary ctypes function-call
  argument does, and an unwrapped/unreferenced callback would also risk
  being garbage-collected out from under mpv later.
- mpv's render-context `update_cb` (fired whenever a new frame is ready)
  runs on mpv's own thread; it does nothing but `frame_ready.emit()`
  (thread-safe from any thread), connected to `VideoSurface.update()` --
  Qt auto-queues that onto the main thread since the emit comes from a
  different thread. Same pattern as the position/duration/pause observers
  below -- never touch a widget directly from an mpv callback.
- Shutdown order matters: free the render context (`VideoSurface.
  release_player()`) *before* terminating the core mpv client
  (`MpvPlayer.shutdown()`) -- `VideoPanel.shutdown()` does this in that
  order.

## Architecture

```
src/vat/
  models/        Plain dataclasses: Label, Cut, ScoreDefinition, VideoEntry,
                 ProjectConfig. JSON round-trippable (to_dict/from_dict),
                 no I/O.
  project/       project_store.py: reads/writes the private project.json
                 (videos_dir, project_dir, labels, scoring config).
                 project.py: Project facade combining project_store +
                 annotation_store so operations spanning both (label/score
                 rename) stay in sync.
  annotations/   annotation_store.py: reads/writes the public
                 annotations.json (video path -> {annotated, cuts[]}).
  media/         video_scanner.py: flat playlist listing of a videos dir
                 + ffprobe duration probing (in-process cached).
  playback/      mpv_player.py (+ _mpv_bootstrap.py) and preloader.py.
  ui/            PySide6 widgets. MainWindow is the controller; every other
                 panel (playlist_panel, video_panel, timeline_widget,
                 inspector_panel) and dialog (label_editor_dialog,
                 score_editor_dialog, project_dialog) is a "dumb" widget
                 that only emits Qt signals and exposes setters -- it does
                 not touch Project or annotation_store directly (dialogs
                 are a partial exception: they hold a Project reference and
                 call it directly, same as label_editor_dialog already did,
                 since they're modal, self-contained CRUD forms rather than
                 part of the always-visible controller wiring). Keep the
                 always-visible panels this way: it's what makes the
                 controller logic testable without a display driving real
                 video playback.
  app.py         QApplication bootstrap / entry point.
  app_settings.py  Tiny ~/Library/Application Support/vat/settings.json
                 for remembering the last-opened project across launches.
```

### Two files per project, on purpose

- `project.json` (private): videos_dir, project_dir, the label set
  (name + shortcut + description), whether scoring is enabled, and the set
  of score definitions (name + min/max + dtype). Internal app config.
- `annotations.json` (**public**, per REQUIREMENT.md #7): video path ->
  `{annotated: bool, cuts: [{id, start, end, label, scores}]}`. Cuts store
  the **label name as a plain string, and score names as plain dict keys**
  (`scores: {"Technique": 87.5}`), not foreign keys into project.json's
  label/score-definition lists. This is deliberate: the annotations file
  must be readable and meaningful entirely on its own. The tradeoff is that
  renaming a label or a score requires rewriting every matching cut across
  the whole annotations file -- `Project.rename_label()` /
  `Project.rename_score_definition()` do this atomically via
  `AnnotationStore.rename_label_everywhere()` /
  `.rename_score_everywhere()`. Don't switch to id-based references without
  revisiting this requirement.

### Scores (per-cut, optional, per-project)

Per REQUIREMENT.md #9. Design decisions made explicitly with the user
before implementing (don't re-litigate without checking back):

- **Each score has its own independent range and dtype** (`min`, `max`,
  `float`/`int`), not one shared range/dtype for the whole project. Same
  pattern as labels already having independent name/shortcut/description.
  `models/score_definition.py`: `ScoreDefinition.coerce(raw_text)` is the
  single source of truth for parsing+range+dtype validation -- both
  `InspectorPanel`'s live "Add Annotation" validation and
  `ScoreEditorDialog` should keep going through it rather than
  reimplementing range checks.
- **A score field added after cuts already exist is *not* retroactively
  enforced.** Existing cuts simply won't have that key in their `scores`
  dict. `Project.is_cut_complete(cut)` / `.missing_scores(cut)` compute
  completeness on the fly against the project's *current* score
  definitions (nothing is stored as an "incomplete" flag) -- `InspectorPanel
  .set_cuts()` uses this to show a "⚠ missing: ..." suffix in the cuts
  list. Purely informational; nothing blocks or auto-fills old cuts.
- **When scoring is enabled, every current score is required to add a new
  cut**, and starts genuinely blank (`QLineEdit` + `QDoubleValidator`, not
  a spin box defaulting to some numeric value -- spin boxes can't
  represent "empty"). `InspectorPanel._refresh_add_button_state()` disables
  "Add Annotation" until every score field parses via `coerce()` without
  error; the first validation error is shown inline. Fields are cleared
  back to blank after a successful add (`clear_pending()`), not left
  showing the last-entered values.
- The "New Cut"/"Add Cut" UI is unconditionally relabeled "New
  Annotation"/"Add Annotation" -- this doesn't toggle based on whether
  *this* project has scoring enabled; a labeled cut is already conceptually
  an annotation, scores are just an optional enrichment of it.
- `ScoreDefinition` has a `description` field (free text, shown in
  `ScoreEditorDialog`'s table and as a tooltip on the corresponding
  `QLineEdit` in `InspectorPanel`) -- same shape as `Label.description`.
- **Editing an existing annotation** (REQUIREMENT.md #10) reuses the same
  label combo + score `QLineEdit`s as adding a new one, rather than a
  separate dialog -- this is why the two action buttons
  (`_edit_cut_btn`, `_add_cut_btn`) sit side by side in
  `InspectorPanel.__init__` (edit on the left/inside, add on the right,
  per explicit user request on button placement). Mechanics:
  - `InspectorPanel._cuts_by_row` stores full `Cut` objects (not just ids)
    so selecting a row has the data needed to populate the fields.
  - `QListWidget.currentRowChanged` (wired once, in `__init__`) is the
    single trigger for "a cut is now selected" -- fires identically
    whether the row was clicked directly, or selected programmatically via
    `select_cut_by_id()` (which is what `TimelineWidget.cut_selected` is
    wired to, so clicking a cut on the timeline/progress bar drives the
    same population path as clicking it in the cuts list).
  - Selecting a cut populates the label combo and each score field with
    that cut's current value, or blanks the field if the cut doesn't have
    a value for that score yet (`cut.scores.get(defn.name)` is `None`) --
    this is *how* an incomplete cut gets filled in: the existing values
    show up prefilled, the missing one is blank and the user fills only
    that. Also clears Mark In/Out on selection -- editing doesn't touch
    timing, and leaving a stale pending range around would let "Add
    Annotation" fire using the just-loaded label/scores, creating an
    accidental duplicate.
  - **`_edit_cut_btn` requires full score validity to enable**, exactly
    like `_add_cut_btn` (shared `_scores_valid()` check) -- not "whatever
    is currently valid, save that." This is a deliberate safety property:
    `AnnotationStore.update_cut(scores=...)` *replaces* the whole scores
    dict when a `scores` argument is passed (see below), so if editing
    were allowed with some fields blank/invalid, saving would silently
    delete previously-recorded values for the fields the user didn't
    touch. Requiring full validity before the button even enables makes
    that data loss structurally impossible rather than something to
    remember to guard against.
  - `MainWindow._on_edit_cut()` calls `Project.update_cut(rel, cut_id,
    label=label, scores=scores)`, then re-selects the same `cut_id` via
    `select_cut_by_id()` after `_refresh_cuts_and_status()` rebuilds the
    list (which otherwise drops the selection) -- this is what makes the
    save visibly "stick" instead of the panel going blank right after
    editing.

### The "annotated" flag is not just "has cuts"

Per `REQUIREMENT.md`'s Definitions section: a video is annotated only once
there's an entry for it (created either by adding a cut, or by an explicit
user confirmation for an intentionally-empty video) **and** the user has
explicitly pressed "mark annotated". Adding cuts alone does not flip
`annotated` to `True` — that requires the explicit confirm action. Both
`AnnotationStore` and the test suite encode this distinction; preserve it.

### TimelineWidget is the *only* scrub control

`VideoPanel` used to also have its own `QSlider` for scrubbing, stacked
right above `TimelineWidget` -- two different circular-handle widgets
doing the same job (reported as confusing; removed). `TimelineWidget` now
owns dragging entirely:

- `mousePressEvent`/`mouseMoveEvent`/`mouseReleaseEvent` implement
  press-and-drag scrubbing directly (no `setMouseTracking` needed -- Qt
  delivers move events while a button is held without it).
- `self._dragging` guards `set_position()`: while `True`, external calls
  (i.e. mpv's async position observer, arriving via
  `VideoPanel.position_changed` -> `TimelineWidget.set_position`) are
  ignored, so the playhead doesn't jitter/fight the mouse from a seek's
  round-trip lag. The drag's own `_seek_to_x()` updates `self._position`
  directly (bypassing that guard, since it's the source of truth during a
  drag) and repaints immediately, so the visual stays smooth regardless of
  when mpv's actual position catches up.
- `mouseDoubleClickEvent` on a cut emits `cut_double_clicked`, wired in
  `MainWindow._on_timeline_cut_double_clicked` to *both* select the cut
  (loads it into the inspector for editing, same as a single click) *and*
  seek playback to its start -- "edit it live," per the request that added
  this. Note Qt's actual event sequence for a double click is press ->
  release -> **doubleclick** -> release, not two presses, so the first
  click's own selection/seek already happened via `mousePressEvent` before
  `cut_double_clicked` fires -- the double-click handler's actions are
  intentionally redundant with that, not a replacement for it.
- Cut label text color is computed via `utils.colors.contrasting_text_color()`
  (YIQ luminance) rather than hardcoded white -- several palette colors
  (e.g. `#bcf60c`, `#fabebe`) are light enough that white text was
  reported as hard to read.

### TransportLineEdit: keeping transport shortcuts alive from a text field

A `QLineEdit`-focused score input silently swallows plain Left/Right/Up/
Down for in-field cursor movement before those key presses ever reach
`QShortcut` dispatch -- no `ShortcutContext` setting fixes this, since
it's the focused widget's own `keyPressEvent` claiming the key, not a
shortcut-routing question. Reported as a real bug (arrow keys going dead
once a score field had focus). Fixed in `ui/widgets.py`:
`TransportLineEdit` intercepts plain (unmodified) arrow keys in its own
`keyPressEvent` *before* calling `super()`, emitting `arrow_key_pressed`
instead of moving the cursor; modified combinations (e.g. Shift+Left for
selection) still fall through to normal `QLineEdit` behavior. All of
`InspectorPanel`'s dynamically-built score fields use this instead of
plain `QLineEdit`, forwarding to `MainWindow._on_navigate_requested()` --
the same handler the global Left/Right/Up/Down `QShortcut`s use, so the
behavior is identical whether or not a score field happens to have focus.
If you add another always-must-work-regardless-of-focus keybinding, route
it through `_on_navigate_requested()`'s direction-string pattern rather
than inventing a new one-off mechanism.

### Playlist annotation counts need an explicit refresh trigger

`PlaylistPanel.set_videos()` takes an optional `cut_counts: dict[str,
int]`, computed in `MainWindow.refresh_playlist()` from
`project.get_entry(rel).cuts`. This is a snapshot, not reactive -- adding,
editing, or deleting a cut only updates `InspectorPanel`/`TimelineWidget`
via `_refresh_cuts_and_status()` unless `refresh_playlist()` is *also*
called. `_on_add_cut()` and `_on_delete_cut()` both call it (the count
changes); `_on_edit_cut()` deliberately doesn't (editing a cut's
label/scores doesn't change how many cuts exist). If you add another
cut-mutating action, decide the same way: does the *count* change, not
just the cut's contents?

## Branches

- `main` is the development branch (default; everything lands here first).
- `stable` (renamed from `prod`) is the "deployment" branch — for this
  project, deployment means the user running the app locally on their own
  Mac. Merge `main` into `stable` only for versions considered
  stable/run-worthy, not on every commit.
- **`main` and `stable` each have their own `README.md`** (`main`'s is
  contributor-facing, `stable`'s is user-facing) -- this is deliberate, the
  project is meant to be pushed to GitHub for others to use and contribute
  to, and those are different audiences with different needs. The
  consequence: promoting `main` into `stable` is **no longer a plain
  fast-forward** (that only worked while the branches were identical) --
  it's a real merge that will conflict on `README.md` every time. Resolve
  by keeping `stable`'s own README and taking everything else from `main`:
  ```bash
  git checkout stable
  git merge main
  git checkout --ours README.md   # keep stable's own README
  git add README.md
  git commit
  ```
  Every other file should merge cleanly and stay in sync between the two
  branches; only `README.md` is intentionally exempt from that.

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
  `MpvPlayer` (real `libmpv`) -- under the offscreen platform, the older
  `wid`-embedding approach **segfaulted the whole test process** this way
  (reproduced once; see git history / CHANGELOG); the current Render-API
  `VideoSurface` degrades more gracefully under offscreen (Qt logs
  `QOpenGLWidget is not supported on this platform` and the render context
  is simply never created), but still don't rely on that -- UI controller
  tests use an *empty* videos directory and poke
  `MainWindow._current_video_path` directly instead, consistent with
  `tests/test_ui_controller.py`. If a test genuinely needs
  `refresh_playlist()` to run against a real file (e.g. to exercise its
  filesystem scan or the annotation-count computation), stub
  `window.video_panel.load = lambda path: None` first so the row-0
  auto-selection cascade can't reach real player construction --
  `test_refresh_playlist_includes_annotation_counts` in
  `test_ui_controller.py` is the reference example.
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
