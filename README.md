# Video Annotation Tool

A lightweight macOS tool for annotating videos with cuts (start/end time +
label) without ever modifying the source video files. It only writes an
annotation mapping file. See `REQUIREMENT.md` for the full spec.

## Requirements

- macOS (developed against macOS Tahoe on Apple Silicon).
- [Homebrew](https://brew.sh).
- `mpv` and `ffmpeg` (for `ffprobe`):

  ```bash
  brew install mpv ffmpeg
  ```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Running

```bash
.venv/bin/vat
# or
.venv/bin/python -m vat
```

On first launch you'll be asked to create a new project (choose a project
directory and a videos directory) or open an existing one. The app
remembers the last-opened project for next time.

## Using it

- **Playlist** (left): pick a videos directory; step through videos like a
  playlist. Each entry shows ● (annotated) or ○ (not annotated).
- **Preview + timeline** (center): plays the selected video in real time;
  the bar beneath it shows existing cuts, color-coded by label. Click to
  seek; click a cut to select it.
- **Inspector** (right): `Mark In` (I) / `Mark Out` (O) capture the current
  playback position, pick a label, then `Add Cut`. Each label can also have
  its own single-key shortcut (set in the label editor) to select it
  quickly. Existing cuts for the video are listed below, double-click to
  seek to one. `Mark Annotated` / `Unmark Annotated` confirms the video's
  annotation status — a video only counts as annotated once you explicitly
  confirm it, even if it has no cuts.
- **File menu**: change the videos directory, move the project directory
  (moves all project files, including the annotations file), or start/open
  another project.
- **Edit > Edit Labels…**: add, remove, or rename labels (and their
  shortcuts). Renaming a label updates it everywhere it's already been used
  across every annotated video.

## Project files

Each project directory contains:

- `project.json` — private app config: videos directory, project directory,
  the label set.
- `annotations.json` — the **public** annotation mapping: for each video
  (by relative path), whether it's annotated and its list of cuts
  (`{id, start, end, label}`). This file is meant to be read/consumed
  independently of the app.

## Development

```bash
.venv/bin/pytest
```

See `CLAUDE.md` for architecture notes and important environment gotchas,
`CHANGELOG.md` for what's changed, and `BACKLOG.md` for what's intentionally
not done yet.

## Branches

- `main` — active development.
- `prod` — the branch actually run day-to-day ("deployment" currently just
  means running this locally on macOS; Homebrew packaging is planned but
  not yet done, see `BACKLOG.md`).
