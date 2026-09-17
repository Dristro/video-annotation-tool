# Video Annotation Tool

A lightweight macOS tool for annotating videos with cuts (start/end time +
label, optionally with named scores and a free-text justification)
without ever modifying the source video files. It only writes an
annotation mapping file. See `REQUIREMENT.md` for the full
functional/non-functional spec.

**You're on `main`, the development branch.** If you just want to run the
app, switch to `stable` — its README covers installing and using it. This
one covers building from source and contributing.

## Building from source

### Prerequisites

- An Apple Silicon Mac running macOS 14 or newer (that's what it's
  developed and tested on; Intel Macs and Linux are a later phase — see
  `BACKLOG.md`).
- [Homebrew](https://brew.sh).
- **Python 3.11 or newer.** Any of these work:
  - the [python.org installer](https://www.python.org/downloads/macos/)
    (what the maintainer uses; also what `scripts/build_app.sh` needs,
    since PyInstaller wants a framework build), or
  - `brew install python@3.12`.
- The two tools video playback and media probing rely on:

  ```bash
  brew install mpv ffmpeg
  ```

  `mpv` provides `libmpv` (playback, via python-mpv); `ffmpeg` provides
  `ffmpeg`/`ffprobe` (thumbnails, waveform, durations). Neither is
  bundled or vendored — the app loads them from Homebrew at runtime.

### Set up and run

```bash
git clone https://github.com/Dristro/video-annotation-tool.git
cd video-annotation-tool
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

.venv/bin/vat                  # run it (opens the last project, or the project dialog)
.venv/bin/vat ~/some/project   # open a specific project directory
.venv/bin/pytest               # run the test suite (headless, ~7 s)
.venv/bin/vat --doctor         # how libmpv/ffmpeg resolved, PATH, DYLD_* — paste into bug reports
```

Activating the venv (`source .venv/bin/activate`) is optional; every
command above works with the explicit `.venv/bin/` prefix.

### Install as a command without the checkout

The project is a standard `pyproject.toml` package with a `vat` console
script, so it can be installed straight from git into any environment
(the Homebrew `mpv`/`ffmpeg` requirement still applies):

```bash
pipx install "git+https://github.com/Dristro/video-annotation-tool.git@stable"
# or, into a venv of your own:
python3 -m venv ~/.vat && ~/.vat/bin/pip install "git+https://github.com/Dristro/video-annotation-tool.git@stable"
```

Publishing to PyPI is not set up yet (`BACKLOG.md`).

### Build the macOS .app

```bash
.venv/bin/pip install -e ".[dev,build]"
scripts/build_app.sh           # -> dist/VAT.app, dist/VAT-<ver>-arm64.zip, .sha256
open dist/VAT.app
```

The bundle still depends on Homebrew's `mpv` and `ffmpeg` (deliberately;
`packaging/README.md` explains why and how releases, the Homebrew cask
and code signing fit together). User-facing install steps are in
`docs/INSTALL.md`.

### If something doesn't work

- `Symbol not found: _CGLGetCurrentContext` — a known macOS/libmpv
  interaction, already worked around in `src/vat/playback/_mpv_bootstrap.py`.
  `CLAUDE.md` documents it in depth.
- The app starts but there are no thumbnails / waveform / durations —
  run `.venv/bin/vat --doctor`; if `ffmpeg` shows `NOT FOUND` or `DYLD_*`
  isn't `none`, that's the cause (see the same section of `CLAUDE.md`).
- A dialog on startup saying `mpv`/`ffmpeg` is missing — run the
  `brew install` line it shows.

## Before you touch anything, read `CLAUDE.md`

It's the durable context for this codebase: the module layout, why certain
things are built the way they are (e.g. why annotations are stored with
plain-string label/score keys instead of ids, why mpv is rendered via its
Render API instead of window embedding, why a `QTimer` was a landmine
around mpv's macOS threading, why the `.app` doesn't bundle libmpv), and
standing rules discovered the hard way that shouldn't get re-broken. If
you're about to add a poll loop touching mpv, or embed a native window,
or shell out to a tool, or change the annotation file's shape —
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
  `tests/test_ui_controller.py`'s pattern for new ones (or stub
  `window.video_panel.load` when a real file must be listed).
- `playback/mpv_player.py` is tested against a fake `mpv` module
  (`tests/test_mpv_player.py`); real playback is manual-only by nature.
- Core logic (models, `project_store`, `annotation_store`, `video_scanner`,
  the `Project` facade, `migrations`) has no Qt/mpv dependency — prefer
  adding coverage there over UI-level tests when the logic doesn't
  actually need a widget.

## Branches

- `main` — active development. Everything lands here first; this is what
  you want to branch a contribution from.
- `stable` — what end users actually run locally. Promoted from `main`
  only when the maintainer says so, after hands-on testing.

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
