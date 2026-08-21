# Video Annotation Tool

A lightweight macOS tool for annotating videos with cuts (start/end time +
label, optionally with named scores) without ever modifying the source
video files. It only writes an annotation mapping file alongside your
videos — the raw footage is never touched.

**You're on the `stable` branch** — this is the version meant to be run.
If you want to build/modify the tool itself, switch to `main`; that
branch's README covers development setup and its `CLAUDE.md` covers the
architecture in depth.

## Requirements

- macOS (developed against macOS Tahoe on Apple Silicon).
- [Homebrew](https://brew.sh).
- `mpv` and `ffmpeg` (for `ffprobe`):

  ```bash
  brew install mpv ffmpeg
  ```

## Install & run

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/vat
# or: .venv/bin/python -m vat
```

On first launch you'll be asked to create a new project (choose a project
directory and a videos directory) or open an existing one. The app
remembers the last-opened project for next time.

## Using it

The layout mirrors DaVinci Resolve: a video playlist on the left, preview +
timeline in the center, and an inspector for annotation actions on the
right.

- **Playlist** (left): pick a videos directory; step through videos like a
  playlist. Each entry shows ● (annotated) or ○ (not annotated).
- **Preview + timeline** (center): plays the selected video in real time;
  drag the position slider to scrub live. The bar beneath the video shows
  existing cuts, color-coded by label — click to seek, click a cut to
  select it (see "editing an annotation" below).
- **Inspector** (right):
  - `Mark In` (I) / `Mark Out` (O) capture the current playback position.
  - Pick a label from the dropdown — each label can have its own custom
    keyboard shortcut (set in the label editor) to select it instantly.
  - If the project has scoring enabled, a required, initially-blank field
    appears for each score the project defines (e.g. "Technique: 0–100").
    Values outside the defined range are rejected.
  - `Add Annotation` creates a new cut from the current Mark In/Out +
    label + scores.
  - **Editing an existing annotation**: click a cut (on the timeline or in
    the Cuts list below) to load its label and scores back into these same
    fields — existing values appear prefilled, anything missing (e.g. a
    score added to the project after this cut was created) shows up
    blank. Fix or fill in what's needed, then click `Edit Annotation`
    (to the left of `Add Annotation`) to save the change onto that same
    cut.
  - Cuts missing a currently-required score are marked "⚠ missing: ..." in
    the list, so incomplete annotations are easy to spot and fix.
  - `Mark Annotated` / `Unmark Annotated` confirms the video's annotation
    status — a video only counts as annotated once you explicitly confirm
    it, even if it has no cuts.
- **File menu**: change the videos directory, move the project directory
  (moves all project files, including the annotations file), or start/open
  another project.
- **Edit menu**:
  - `Edit Labels…` — add, remove, or rename labels and their shortcuts.
    Renaming a label updates it everywhere it's already been used.
  - `Edit Scores…` — turn per-cut scoring on/off for the project, and
    manage the set of named scores (each with its own range, whole-number
    or decimal type, and a description shown here and as a tooltip when
    entering a value). Renaming a score updates it everywhere it's already
    been recorded.

## Project files

Each project directory contains:

- `project.json` — private app config: videos directory, project
  directory, the label set, and (if enabled) the project's score
  definitions.
- `annotations.json` — the **public** annotation mapping: for each video
  (by relative path), whether it's annotated and its list of cuts
  (`{id, start, end, label, scores}`). This file is meant to be
  read/consumed independently of the app — labels and score names are
  stored as plain text, not internal ids, so it's self-describing on its
  own.

## Contributing

This branch is for running the app. Development happens on `main` — see
that branch for setup instructions, testing, and `CLAUDE.md` for
architecture notes and design decisions.
