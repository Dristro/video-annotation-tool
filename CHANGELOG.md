# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added: GitHub Actions CI running pytest

- **Added**: `.github/workflows/tests.yml` runs the full `pytest` suite on
  push to `main`/`stable` and on pull requests. Runs on a `macos-latest`
  runner (not Linux) with `brew install mpv ffmpeg`, since `vat.ui.*`
  modules import `mpv_player.py` transitively (even though no test ever
  constructs a real `MpvPlayer`), so libmpv has to be loadable just for
  the suite to collect.

### Added: direct tests for Preloader

- **Added**: `Preloader` never touches libmpv (only `probe_duration()` and
  a plain file read), so unlike `mpv_player.py` it's actually unit
  testable — added coverage for the in-flight dedup behavior (a second
  `preload()` call while one is running is a no-op, not queued), a
  missing-file path not raising, and a new call being accepted once the
  previous one finished.
- 4 new tests (209 total).

### Added: "Open Recent" projects submenu

- **Added**: File > Open Recent lists up to 8 previously-opened project
  directories (most-recent-first, current project excluded from its own
  list), stored alongside the existing single "last opened" setting in
  `~/Library/Application Support/vat/settings.json`. `app_settings
  .save_last_project_dir()` now read-modify-writes that file instead of
  blindly overwriting it, which would otherwise have wiped the new
  `recent_project_dirs` list every time a project was opened.
- 8 new tests (205 total).

### Added: short id tag distinguishes which cuts a continuation link pairs

- **Added**: cuts with a continuation link now show a short 4-char tag
  derived from their `continuation_id` (e.g. `#a1b2`) next to the →/←
  marker — on the timeline (rectangle label + hover tooltip) and in the
  inspector's cuts list. Two cuts that link to each other always show the
  same tag, so with several continuing cuts in a project it's now
  possible to tell which pairs go together without matching label/timing
  by eye. New `_continuation_tag()` helper in `timeline_widget.py`,
  reused by `inspector_panel.py`.
- 8 new tests (197 total).

### Added: handle more than one pending continuation from the previous video

- **Added**: `Project.pending_continuations()` (new, plural) returns every
  uncompleted `continues_forward` cut left by the previous video, not just
  the first — the data model never prevented more than one, but the UI
  only ever surfaced one. `pending_continuation()` (singular) is now a
  thin wrapper returning the first match, kept for the common case. The
  inspector's continuation banner shows a "Next" button (with a "(i/N)"
  count) when there's more than one, and "Start Here" acts on whichever
  one is currently shown.
- 9 new tests (193 total).

### Added: break a cut's continuation link

- **Added**: selecting a cut that has a continuation link (either half)
  now shows a "Break Continuation Link" button in the inspector, which
  clears its `continuation_id`/`continues_forward` (confirmed via a
  dialog first). Previously the only way to undo a link was deleting one
  of the two linked cuts entirely. `AnnotationStore.break_continuation()`
  is a dedicated method, kept separate from `update_cut()` (which
  deliberately never touches these fields on an ordinary edit — see the
  earlier continuation-drop bugfix entry below). Starting a *new* link is
  still only possible at creation time via the checkbox/banner; re-linking
  to a *different* cut after breaking isn't supported (BACKLOG.md).
- 6 new tests (186 total).

### Added: re-time an existing annotation via Edit Annotation

- **Added**: Edit Annotation can now adjust a cut's start/end, not just
  its label/scores. Previously the only way to change timing was delete +
  re-add. Mark In/Out are cleared (not pre-filled) on selecting a cut, same
  as before — clicking Edit Annotation with both still unset keeps the
  cut's existing timing; explicitly pressing Mark In and/or Mark Out
  before clicking Edit Annotation re-times it to the new range. Half-set
  (only one of Mark In/Out touched) disables the button, same rule as Add
  Annotation. Re-timing into an overlap with another cut on the same video
  prompts for confirmation, reusing `Project.overlapping_cuts()`.
- 7 new tests (180 total).

### Added: single "Project Settings…" dialog for labels + scores

- **Added**: `ProjectSettingsDialog` merges label and score management
  into one tabbed dialog ("Labels" / "Scores"), replacing the separate
  "Edit Labels…" / "Edit Scores…" menu items and dialogs.
  `LabelEditorDialog`/`ScoreEditorDialog` still exist as standalone
  wrappers (their table/CRUD logic was extracted into `_LabelsWidget`/
  `_ScoresWidget`, embedded by both the standalone dialogs and the new
  tabbed one) but are no longer wired into `MainWindow`'s menu.
- 5 new tests (173 total).

### Added: score values on timeline hover tooltip

- **Added**: hovering a cut on `TimelineWidget` now shows a tooltip with
  its time range, label, and any recorded score values — previously
  scores were only visible in the inspector's cuts list text.
- 2 new tests (168 total).

### Added: delete confirmation, duplicate-shortcut warning, overlap warning

- **Added**: deleting a cut now shows a Yes/No confirmation ("This cannot
  be undone.") instead of deleting immediately — no undo exists yet
  (`BACKLOG.md`), so this is the only safety net for now.
- **Added**: `LabelEditorDialog` warns (non-blocking) when a label's
  shortcut collides with another label's — previously the last-registered
  `QShortcut` silently won and the other label's shortcut just never
  fired, with no indication why.
- **Added**: adding an annotation that overlaps an existing one on the
  same video now prompts for confirmation first. Overlaps are still
  allowed (REQUIREMENT.md doesn't forbid them) — this only surfaces the
  case in case it's accidental. `Project.overlapping_cuts()` is the new
  reusable check (half-open interval overlap, `start < other.end and
  other.start < end`).
- 10 new tests (163 total).

### Fixed: editing an annotation silently severed its cross-video continuation link

- **Fixed**: `AnnotationStore.update_cut()` rebuilt the cut's dataclass
  without carrying over `continuation_id`/`continues_forward`, so clicking
  "Edit Annotation" on *any* cut that was part of a cross-video
  continuation link (REQUIREMENT.md #11) reset those fields to their
  defaults and silently broke the link, even when only the label or a
  score was changed. Found during a documentation-verification pass, not
  reported by a user. Now preserved across `update_cut` unless a future
  caller explicitly changes them (nothing currently does).
- 1 new regression test (153 total):
  `test_update_cut_preserves_continuation_fields`.

### Added/Fixed: playback speed control, play/pause button resize bug
(REQUIREMENT.md #12, `main` only)

- **Fixed**: the Play/Pause button visibly resized (shifting everything
  else in the transport row) every time playback toggled, since "Play"
  and "Pause" aren't the same width. Now sized once via `QFontMetrics` to
  fit whichever is wider.
- **Added**: a notched playback speed slider (0.25x-2x, `SPEED_STEPS` in
  `ui/video_panel.py`), placed inline with the play/pause button and
  elapsed-time display, at the right-hand end of that row. An integer
  `QSlider` over step indices rather than a continuous range, so it can
  only ever land on one of the defined speeds. `MpvPlayer.set_speed()`
  added as a discrete, user-driven property set (same category as
  existing seek/pause controls, not a recurring poll). Speed persists
  across videos within a session, matching typical media player behavior.
- 11 new tests (152 total): `format_time`, fixed-width button sizing
  (including across repeated toggles), and the speed slider's default/
  range/label-update/no-player-safety behavior.

### Added: cross-video continuing annotations (REQUIREMENT.md #11, `main`
only)

- An annotation can now continue past one video's end into the start of
  the next video in the playlist. Checking "Continues into next video"
  while adding a cut marks it as the front half (its end becomes this
  video's own end automatically -- Mark Out is no longer required, or
  used, when this is checked) and mints a shared link id. Opening the
  following video shows a banner ("⚠ Continuing 'goal' from previous
  video") with a "Start Here" button that pre-fills the label/scores and
  sets Mark In to 0:00; the user marks where it actually ends and clicks
  Add Annotation to complete the link.
- Both ends are opt-in -- nothing is auto-created; the link only exists
  once the user completes it on the following video.
- Chains across 3+ videos work without any extra structure: a middle
  video's cut can simultaneously complete the incoming link and continue
  it forward, by reusing (not regenerating) the same link id -- the
  matching logic (`Project.pending_continuation`) only ever checks one
  hop of playlist adjacency at a time, so one shared id threaded through
  every cut in the chain still links each adjacent pair correctly.
- `Cut` gained `continuation_id`/`continues_forward`; the timeline and
  cuts list show a →/← marker on linked cuts.
- Design (three options: simple visual flags only, this linked
  carry-forward approach, or a full multi-segment annotation schema) was
  confirmed with the user before implementing.
- 21 new tests (141 total): `Cut` continuation fields, `Project
  .pending_continuation()` (including the 3-video chain case),
  `PlaylistPanel.previous_path()`/`next_path()`, `InspectorPanel`'s
  checkbox/banner/prefill behavior, and a full `MainWindow`-level
  two-video flow.
- Verified end-to-end via a scripted (non-pytest) run against real files
  with `video_panel.load` stubbed, after first reproducing and fixing a
  bug in the verification script itself (not the source) where
  `_on_add_cut`'s own `refresh_playlist()` call was wiping out a
  synthetically-injected playlist mid-test.

### Added/Changed: playlist counts, single scrub control, timeline
double-click edit, contrast fix, arrow-key bug fix (`main` only --
not yet promoted to `stable`)

- **Playlist annotation counts**: each video in the left-hand playlist now
  shows how many cuts it has (e.g. "a.mp4 (3)"), alongside the existing
  ●/○ annotated marker. `PlaylistPanel.set_videos()` takes an optional
  `cut_counts` dict; `MainWindow` recomputes and passes it after any
  add/delete (not edit -- edit doesn't change the count).
- **Removed the video panel's own position slider** -- it duplicated
  `TimelineWidget`'s scrubbing (two circular-handle controls doing the
  same job, reported as confusing). `TimelineWidget` is now the sole
  scrub control: press-and-drag anywhere on it to scrub live (added
  `mouseMoveEvent`-driven dragging with a guard so mpv's async position
  updates can't fight the drag visually).
- **Double-click a cut on the timeline** to select it (loading it into the
  inspector for editing, same as a single click) *and* seek playback to
  its start in one action -- "edit it live."
- **Fixed low-contrast label text on the timeline**: cut labels now use
  black or white text based on the background color's luminance instead
  of hardcoded white, which was unreadable against several of the
  lighter palette colors.
- **Fixed a real bug**: once a score field had keyboard focus, Left/Right/
  Up/Down stopped working for transport/playlist navigation entirely --
  `QLineEdit` claims plain arrow keys for in-field cursor movement before
  they ever reach shortcut dispatch. New `TransportLineEdit` (`ui/
  widgets.py`) intercepts them and forwards to the same handler the
  global shortcuts use. **Up/Down are also new** -- there was previously
  no keyboard shortcut for stepping to the previous/next video in the
  playlist at all; added both as global shortcuts and via score fields'
  arrow keys.
- REQUIREMENT.md: extended non-functional requirement #9 (annotation
  count) and added #10 (keyboard navigation must keep working regardless
  of focus).
- 26 new tests (120 total): `TimelineWidget` drag/double-click behavior,
  `TransportLineEdit` key interception, `contrasting_text_color`,
  `PlaylistPanel` counts/`select_relative`, and `MainWindow` wiring for
  all of the above.

### Changed: `prod` branch renamed to `stable`; per-branch READMEs

- Renamed the `prod` branch to `stable` (same purpose: what end users run
  locally). Ahead of pushing this project to GitHub for others to use and
  contribute to.
- `main` and `stable` now each carry their own `README.md` -- `main`'s is
  contributor-facing (dev setup, testing conventions, pointers to
  `CLAUDE.md`), `stable`'s is user-facing (install/run/usage walkthrough).
  Documented the resulting workflow change in `CLAUDE.md`: promoting
  `main` into `stable` is now a real merge (conflicts on `README.md` every
  time, resolved by keeping `stable`'s own copy), not a plain fast-forward
  like before.

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
