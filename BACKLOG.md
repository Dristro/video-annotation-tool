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
      `stable` branch locally.
- [ ] `vat` command currently requires the repo's venv on PATH; no
      standalone binary yet.

## UI / UX polish (DaVinci-Resolve-likeness)

- [ ] Thumbnail previews in the playlist panel (currently text + a
      colored ●/○ annotated marker only).
- [ ] Waveform/audio preview under the timeline.
- [ ] Drag-to-resize cut edges directly on the timeline, instead of only
      Mark In / Mark Out buttons + a separate "Add Cut" action.
- [ ] Undo/redo only covers cut add/edit/delete (`UndoStack` in
      `project/undo_stack.py`, wired in `MainWindow`), not label/score
      renames -- those propagate across every video's cuts via
      `rename_*_everywhere` and would need a full before/after snapshot of
      every affected cut to undo cleanly. `_on_break_continuation()` also
      isn't on the undo stack yet.

## Scores follow-ups

## Cross-video continuation follow-ups

- [ ] Breaking a continuation link (via the "Break Continuation Link"
      button, shown when the selected cut has one) is supported now, but
      *starting* a new one is still only possible at creation time via the
      checkbox/banner, and there's no way to re-link a cut to a
      *different* other cut once broken (only delete + re-add).
## Correctness / robustness

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

- [ ] `playback/mpv_player.py` has no direct automated tests — real libmpv
      playback isn't meaningfully unit testable, and embedding it in an
      offscreen/headless window segfaults (see `CLAUDE.md`). Covered only
      indirectly via manual runs. (`playback/preloader.py` now has direct
      tests — it never touches libmpv, only `probe_duration()`/file I/O.)

## Explicitly out of scope (per REQUIREMENT.md)

- Actual video re-encoding / clip file generation — this tool only ever
  writes start/end/label mappings, never touches or exports raw video
  files. Don't add "export clip" functionality without checking back on
  this constraint.
