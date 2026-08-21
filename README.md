# Video Annotation Tool

A lightweight macOS tool for annotating videos with cuts (start/end time +
label, optionally with named scores) without ever modifying the source
video files. It only writes an annotation mapping file. See
`REQUIREMENT.md` for the full functional/non-functional spec.

**You're on `main`, the development branch.** If you just want to run the
app, switch to `stable` — its README covers installing and using it. This
one covers building and contributing.

## Dev setup

```bash
brew install mpv ffmpeg   # runtime deps
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/vat                  # run it
.venv/bin/pytest               # run the test suite
```

## Before you touch anything, read `CLAUDE.md`

It's the durable context for this codebase: the module layout, why certain
things are built the way they are (e.g. why annotations are stored with
plain-string label/score keys instead of ids, why mpv is rendered via its
Render API instead of window embedding, why a `QTimer` was a landmine
around mpv's macOS threading), and standing rules discovered the hard way
that shouldn't get re-broken. If you're about to add a poll loop touching
mpv, or embed a native window, or change the annotation file's shape —
`CLAUDE.md` almost certainly already has an opinion on it.

Also see `CHANGELOG.md` (what's shipped, Keep-a-Changelog style) and
`BACKLOG.md` (known gaps and deferred work — check here before assuming
something's an oversight rather than a documented gap).

## Testing conventions

- The suite runs headless (`QT_QPA_PLATFORM=offscreen`, set in
  `tests/conftest.py`).
- **Never let a test cause a real video to be selected** while the videos
  directory is non-empty at `MainWindow` construction — that constructs a
  real `MpvPlayer`/libmpv instance, which needs a real display. UI
  controller tests use an empty videos directory and poke
  `MainWindow._current_video_path` directly instead; follow
  `tests/test_ui_controller.py`'s pattern for new ones.
- Core logic (models, `project_store`, `annotation_store`, `video_scanner`,
  the `Project` facade) has no Qt/mpv dependency — prefer adding coverage
  there over UI-level tests when the logic doesn't actually need a widget.

## Branches

- `main` — active development. Everything lands here first; this is what
  you want to branch a contribution from.
- `stable` — what end users actually run locally ("deployment" currently
  just means running this on your own Mac; Homebrew packaging is planned,
  see `BACKLOG.md`).

**Each branch has its own README** (this one is contributor-facing,
`stable`'s is user-facing), so promoting `main` into `stable` is a real
merge, not a fast-forward — it will conflict on `README.md` every time.
Resolve by keeping `stable`'s own README and taking everything else from
`main`:

```bash
git checkout stable
git merge main
# resolve the README.md conflict:
git checkout --ours README.md
git add README.md
git commit
```

Only promote versions considered stable/run-worthy, not every commit.

## Contributing

- Keep `CHANGELOG.md` and `BACKLOG.md` updated as you go — they're read
  before code archaeology, not after.
- Commit incrementally with descriptive messages rather than batching
  unrelated changes.
- If you change something `CLAUDE.md` documents an opinion about, update
  that opinion in the same change rather than leaving it stale.
