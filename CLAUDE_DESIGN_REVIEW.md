# CLAUDE.md verification pass (2026-08-22)

Cross-checked every design claim in `CLAUDE.md` against the current state of
`src/vat/**` (all ~3,100 lines read directly, not sampled) and `tests/**`.
Below: two real findings worth fixing, plus draft prose for design aspects
that exist in the code but aren't written down in `CLAUDE.md` yet. Nothing
in `CLAUDE.md`'s existing prose was found to be factually wrong about
current architecture — the two issues below are a stale comment and a real
bug, not documentation errors.

Everything after "### Draft additions" is written in `CLAUDE.md`'s own voice
and citation style, ready to paste into the relevant sections.

---

## 1. Correctness bug: `AnnotationStore.update_cut` silently drops continuation fields

`src/vat/annotations/annotation_store.py`, `update_cut()`:

```python
updated = Cut(id=cut.id, start=new_start, end=new_end, label=new_label, scores=new_scores)
```

This rebuilds the `Cut` without carrying over `continuation_id` /
`continues_forward` from the cut being replaced — both silently reset to
their dataclass defaults (`None` / `False`). Every caller of `update_cut`
goes through this same path, including `MainWindow._on_edit_cut()` (wired
to the "Edit Annotation" button), which only ever passes `label=` and
`scores=`.

Net effect: clicking **Edit Annotation** on *any* cut that's part of a
cross-video continuation chain (REQUIREMENT.md #11) — front half, back
half, or a middle link — severs that cut from the chain the moment you
save, even though the user only touched the label or a score field. This
is stronger than the known/accepted gap already recorded in `BACKLOG.md`
under "Cross-video continuation follow-ups" ("Edit Annotation can't change
a cut's continuation status... same scoping decision as the label+scores-
only edit limitation") — that entry describes an inability to *add* or
*change* continuation status via edit, framed as an intentional scope
limit. What actually happens is edit *destroys* continuation status that
was already there, which isn't the same thing and isn't called out
anywhere. No test in `tests/test_annotation_store.py` covers a
continuation-linked cut going through `update_cut`, which is why this
wasn't caught.

Fix is small — carry the two fields through in the rebuilt `Cut`:
```python
updated = Cut(
    id=cut.id, start=new_start, end=new_end, label=new_label, scores=new_scores,
    continuation_id=cut.continuation_id, continues_forward=cut.continues_forward,
)
```
Flagging rather than fixing since fixing wasn't asked for — happy to patch
it plus add a regression test if wanted.

## 2. Stale comment: `MainWindow.__init__`'s `QTimer.singleShot` rationale describes the old `wid` approach

`src/vat/ui/main_window.py`, lines ~73–84, the comment justifying
`QTimer.singleShot(0, self.refresh_playlist)` still says:

> "...auto-select the first video, which loads it into VideoPanel and
> constructs a real MpvPlayer -- which calls `surface.winId()` to hand mpv
> a native window to embed into..."

`winId()` is not called anywhere in the current codebase (confirmed via
grep — the only hit is this comment itself). The app moved to the Render
API (`VideoSurface.bind_player()` / `mpv.MpvRenderContext`, no window
handoff) per `CLAUDE.md`'s own "Video rendering architecture" section. The
underlying *reason* for the deferred call may still be valid (constructing
`MpvPlayer`/`VideoSurface` before the window is shown could plausibly still
misbehave under the Render API too, since `initializeGL()` needs a real,
current GL context), but the comment's specific mechanism (`winId()`) is
describing a code path that was removed. Worth a one-line edit so a future
reader doesn't go looking for a `winId()` call that isn't there. Did not
edit it since only a review was requested.

---

## Draft additions

These are real, deliberate design properties visible in the code that
`CLAUDE.md` doesn't currently mention. Grouped so each can be dropped into
the section it belongs under.

### Under "Architecture" — error hierarchy

`src/vat/errors.py` defines a single-root exception hierarchy
(`VatError` -> `ProjectError` -> `ProjectAlreadyExistsError` /
`ProjectNotFoundError` / `DuplicateLabelError` / `LabelNotFoundError` /
`DuplicateScoreDefinitionError` / `ScoreDefinitionNotFoundError` /
`CutNotFoundError`). `ProjectStore`/`AnnotationStore`/`Project` raise these
instead of bare `ValueError`/`KeyError`, and the UI layer (dialogs,
`MainWindow`) catches the specific subclasses to show a `QMessageBox`
rather than letting an exception reach the Qt event loop. If you add a new
failure mode that a dialog needs to catch and show to the user, add a new
`VatError` subclass here rather than raising a built-in exception — the
dialogs are written to expect this hierarchy (e.g.
`LabelEditorDialog._on_edit` catches `(DuplicateLabelError,
LabelNotFoundError)` specifically).

### Under "Two files per project, on purpose" — `ScoreDefinition.coerce` is also the rename-validation path

Not just live-input validation: `ProjectStore.rename_score_definition()`
rebuilds the *entire* `ScoreDefinition` via its constructor (`__post_init__`)
rather than assigning fields one at a time, specifically so that changing a
score's range or dtype goes through the same min<max /
whole-numbers-for-int checks as creating a new one — an edit that would
produce an invalid definition (e.g. min >= max) raises before it's saved,
rather than silently corrupting the project config. Same defensive pattern
as `Cut.__post_init__` validating `start`/`end`/non-negativity on every
construction, not just at the UI boundary.

### New subsection — Preloading (`playback/preloader.py`)

`MainWindow._on_video_selected()` fires `Preloader.preload(next_path)` for
whatever video is next in the playlist, on a background daemon thread. It
deliberately does two cheap things and nothing more: probes duration via
`probe_duration()` (which also warms `video_scanner`'s in-process duration
cache, so the playlist doesn't re-shell out to `ffprobe` when that video is
actually opened) and reads the first 8 MiB of the file into memory and
immediately discards the buffer. The discard is the point — the goal is to
get those bytes into the *OS* page cache (so mpv's own read-ahead starts
hot when the user actually switches videos), not to hold them in the app's
own RAM, which would fight the <4GB budget in REQUIREMENT.md's
non-functional requirements. `Preloader.preload()` is a no-op if a preload
is already in flight (checked via a `Lock` + `Thread.is_alive()`) rather
than queuing — only the *next* video is ever worth warming, so a stale
in-flight preload for a video the user already skipped past is simply
abandoned, not cancelled or replaced.

### New subsection — Color assignment is deterministic, not stored

`utils/colors.py`'s `color_for_label()` picks a color by hashing the label
*name* (`sha1(name) % len(_PALETTE)`, a fixed 15-entry palette) rather than
storing a color on `Label` or assigning one at creation time. This means
label colors are consistent across the whole app (playlist, timeline)
without needing a `color` field anywhere in `project.json`, and they follow
a label automatically through a rename (same name -> same hash -> same
color, until the name itself changes, at which point the color changes too
as a side effect — this is accepted, not worked around).
`contrasting_text_color()` picks black/white text via YIQ perceptual
luminance against whatever color came out of that hash, rather than
hardcoding white, since several palette entries (`#bcf60c`, `#fabebe`) are
light enough that white text was reported as unreadable on them (already
documented in `CLAUDE.md`'s TimelineWidget section — the *hash-based,
unstored* part of this is what's missing).

### New subsection — `ScoreEditorDialog`/`LabelEditorDialog` write through immediately, not on dialog Accept

Both editor dialogs call `self._project.add_label(...)` /
`rename_label(...)` / `remove_labels(...)` (and the score equivalents)
directly inside each row-level Add/Edit/Remove handler, each of which
calls `ProjectStore.save()` synchronously — not staged in the dialog and
flushed once on OK. The dialogs' own `QDialogButtonBox` only has a single
"Close" button (`accepted`/`rejected` both wired to `self.accept()`), i.e.
there's no Cancel-to-discard path once you've used Add/Edit/Remove inside
the dialog; every row action is already durable on disk before the dialog
closes. `ScoreEditorDialog`'s "Enable scoring" checkbox is the same —
`_on_toggle_enabled` calls `project.set_scoring_enabled()` (and thus
`save()`) the instant it's toggled, not on dialog close. If you add a new
field to either dialog, follow this pattern (write on the action, not on
accept) rather than introducing a staged/discardable edit — nothing else
in the codebase currently supports "cancel to discard a project-level
edit," and mixing the two models in one dialog would be confusing.

### New subsection — `NewProjectDialog` reuses `_LabelFormDialog` across two call sites

`ui/project_dialog.py`'s `NewProjectDialog` imports and reuses
`label_editor_dialog._LabelFormDialog` (a "private" `_`-prefixed class)
directly rather than duplicating the name/description/shortcut form. This
is the one cross-module reach into another dialog module's private class
in the UI layer — if `_LabelFormDialog`'s constructor signature changes,
check `project_dialog.py`'s `_add_label()` too, since nothing else enforces
that link (no shared interface/base class, just the import).

### Under "Testing conventions" — video duration probing is cached per-path, forever, in-process

`video_scanner.probe_duration()` caches by absolute path in a plain
module-level `dict`, with no invalidation and no TTL, for the lifetime of
the process. This is why `Preloader`'s duration probe (a background thread)
and `MainWindow._on_video_selected()`'s own `probe_duration()` call (main
thread, right after `video_panel.load()`) don't race destructively on the
same subprocess spawn for the same file — whichever runs first populates
the cache and the other just reads the dict. (`dict.get`/`dict.__setitem__`
on a single key from two threads is safe under CPython's GIL for this
access pattern; there's no lock around `_duration_cache` and none is
needed here.) If a video file could ever be replaced at the same path
during a session (not a scenario this app currently supports — videos are
never written to), this cache would go stale; worth remembering if that
assumption ever changes.

---

## Things checked and found already accurate (no action)

- The mpv Render API / `wid`-embedding history, the `LC_NUMERIC` /
  `_CGLGetCurrentContext` bootstrap workarounds, and the synchronous-getter
  deadlock story in `CLAUDE.md` all match `_mpv_bootstrap.py` and
  `mpv_player.py` exactly as described.
- `TimelineWidget`'s drag-guard (`_dragging`), `TransportLineEdit`'s
  arrow-key interception, the continuation one-hop-matching logic in
  `Project.pending_continuation()`, and the playlist-count refresh-trigger
  discipline in `MainWindow` all match code exactly as `CLAUDE.md`
  describes them.
- `AnnotationStore`'s "annotated is not just has cuts" distinction is
  correctly implemented (`set_annotated`/`is_annotated` are independent of
  `cuts`).
- Two-files-per-project separation (`project.json` private,
  `annotations.json` public, string/key-based label+score references) is
  implemented exactly as documented, including the `rename_*_everywhere`
  propagation paths (label rename propagation works correctly — only the
  *continuation fields* on the generic `update_cut` path have the bug
  above; label/score renames go through separate, dedicated methods on
  `AnnotationStore` that don't have this issue).
