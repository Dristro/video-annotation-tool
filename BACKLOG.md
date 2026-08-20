# Backlog

Things intentionally deferred, known gaps, and ideas for later. Not a
promise of order — just so nothing gets silently lost. Move items to
`CHANGELOG.md` under `[Unreleased] -> Added` once actually implemented.

## Packaging / distribution

- [ ] Package as a `.app` bundle (PyInstaller or similar) so it's launchable
      without an active venv.
- [ ] Publish a Homebrew formula/cask so `brew install vat` + running `vat`
      from any Terminal works, per the user's stated long-term plan. Explicitly
      out of scope for now — current "deployment" is just running from the
      `prod` branch locally.
- [ ] `vat` command currently requires the repo's venv on PATH; no
      standalone binary yet.

## UI / UX polish (DaVinci-Resolve-likeness)

- [ ] Thumbnail previews in the playlist panel (currently text + a
      colored ●/○ annotated marker only).
- [ ] Waveform/audio preview under the timeline.
- [ ] Drag-to-resize cut edges directly on the timeline, instead of only
      Mark In / Mark Out buttons + a separate "Add Cut" action.
- [ ] Dark theme / visual polish matching DaVinci Resolve's actual palette
      and spacing — current layout matches the *arrangement* (playlist /
      preview / timeline / inspector) but not the visual styling.
- [ ] Confirmation prompt before deleting a cut (currently immediate,
      no undo).
- [ ] Undo/redo for cut edits and label changes.
- [ ] "Recent projects" list (currently only remembers the single
      last-opened project).

## Scores follow-ups

- [ ] `NewProjectDialog` (the project-creation wizard) only lets you set
      initial labels, not initial score definitions or enable scoring --
      scoring can only be configured *after* creating the project, via
      **Edit > Edit Scores…**. Fully functional, just an inconsistency
      with how labels are handled at creation time.
- [ ] Score values aren't shown anywhere on the timeline visualization
      (only in the inspector's cuts list text, e.g. "Technique=87.5,
      Confidence=4"). Could add as a tooltip on hover.
- [ ] "Edit Scores…" and "Edit Labels…" are separate dialogs/menu items;
      no single "Project Settings" dialog exists yet as project-level
      config surfaces grow (videos dir, project dir, labels, scoring are
      all in different menu entries right now).
- [ ] Editing an existing annotation only covers label + scores; the
      start/end time can't be adjusted after the cut is created (only via
      delete + re-add). Deliberately out of scope for the edit-annotation
      feature as requested (focused on filling in/correcting scores), but
      worth revisiting if re-timing existing cuts turns out to matter.

## Correctness / robustness

- [ ] Detect and warn on duplicate label shortcut keys (currently the last
      registered `QShortcut` for a colliding key silently wins).
- [ ] Warn/handle overlapping cuts within the same video (currently allowed
      silently; may or may not be desired).
- [ ] `video_scanner.list_videos` only scans the top level of the videos
      directory (flat playlist, matching "move through all videos in dir
      like a playlist"). No option yet for recursive/subfolder scanning if
      that turns out to be needed.
- [ ] No `project.json` / `annotations.json` schema migration logic beyond
      a `schema_version` field existing — will need real migration code the
      first time the schema changes shape.

## Performance / non-functional requirements

- [ ] RAM/CPU/GPU usage is *bounded* (demuxer cache capped at 64MiB,
      8MiB preload chunks) but not actually *measured* against the <4GB
      budget on real footage. Needs a manual profiling pass (Activity
      Monitor / `footprint`) with real multi-minute video files.
- [ ] Playback speed for sub-5-minute videos has not been benchmarked
      against the requirement, only exercised functionally.
- [ ] `Preloader` warms the OS page cache with a fixed 8MiB head-read; the
      "fetch a starting chunk, load the remainder after it's in the
      rendering region" requirement is satisfied by mpv's own bounded
      demuxer readahead rather than explicit chunked loading logic in our
      code. Revisit if real-world stutter is observed on large files.

## Verification gaps

- [ ] A background-launched instance in the agent's own (non-interactive,
      no WindowServer session) test shell has now consistently
      self-terminated ~15-20s after launch with a clean exit (empty log, no
      crash) across **two structurally different playback implementations**
      (the old `wid`-embedding approach and the current Render API one) --
      since the behavior is identical across two very different pieces of
      code, that's reasonably strong evidence it's an artifact of testing a
      GUI app from a detached/headless shell with no real WindowServer
      session, not a bug in either implementation. Still not proven either
      way. **If the app closes itself unexpectedly after ~15-20 seconds
      during normal interactive use, report it.**
- [ ] The Render API rewrite (see `CLAUDE.md`) was verified structurally
      (compiles, constructs under `QT_QPA_PLATFORM=offscreen` without
      crashing, and -- critically -- loads and plays a real video for ~10s
      in a real, non-offscreen launch without the exception/deadlock/hang
      the two previous `wid`-based attempts hit) but **not** visually --
      the agent's shell has no attached display, so whether the video
      actually now renders *inside* the main window (not a separate one)
      and whether the close (red) button now works have not been confirmed
      by the agent. Please verify both directly.

- [ ] The agent's shell environment has no attached interactive GUI/display
      session (confirmed: `screencapture` and `System Events` can't see the
      launched process's window), so the actual rendered UI has only been
      verified by launching the real (non-offscreen) app against a real
      project + real ffmpeg-generated test video and confirming it stays
      alive with no crash -- not by visually inspecting the layout. **Please
      run `.venv/bin/vat` yourself and sanity-check the actual look/feel**
      (panel proportions, timeline rendering, DaVinci-Resolve-likeness)
      before relying on it.

## Testing gaps

- [ ] `playback/mpv_player.py` and `playback/preloader.py` have no direct
      automated tests — real libmpv playback isn't meaningfully unit
      testable, and embedding it in an offscreen/headless window segfaults
      (see `CLAUDE.md`). Covered only indirectly via manual runs.
- [ ] No CI workflow configured yet (e.g. GitHub Actions running `pytest`
      on push).

## Explicitly out of scope (per REQUIREMENT.md)

- Actual video re-encoding / clip file generation — this tool only ever
  writes start/end/label mappings, never touches or exports raw video
  files. Don't add "export clip" functionality without checking back on
  this constraint.
