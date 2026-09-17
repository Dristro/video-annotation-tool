# Backlog

Things intentionally deferred, known gaps, and ideas for later. Not a
promise of order — just so nothing gets silently lost. Move items to
`CHANGELOG.md` under `[Unreleased] -> Added` once actually implemented.

Status as of 2026-09-17 (the "launch prep" pass): everything that was in
here and implementable without a decision from the user has been done —
see `CHANGELOG.md [Unreleased]`. What's left is either a later phase
("any Mac / Linux"), needs the user's own hands, or is polish.

## Packaging / distribution

- [x] `.app` bundle (PyInstaller): `scripts/build_app.sh` →
      `dist/VAT.app` + zip + sha256. See `packaging/README.md`.
- [x] Homebrew cask: `packaging/homebrew/Casks/vat.rb`, released via
      `.github/workflows/release.yml`. **Needs the user to:** create the
      `Dristro/homebrew-vat` tap repo, push a `v1.0.0` tag, and copy the
      release's `vat.rb` into the tap (steps in `packaging/README.md`).
- [x] `vat` on the command line without the venv — the cask symlinks the
      bundle's binary as `vat`.
- [ ] **Code signing / notarization.** Ad-hoc only until a Developer ID
      exists; Gatekeeper makes users right-click > Open once. The build
      script and release workflow already have the hooks
      (`VAT_SIGN_IDENTITY`, `VAT_NOTARY_PROFILE`).
- [ ] **Bundle libmpv/ffmpeg** so Homebrew isn't required at all. Chosen
      against for this phase (relinking ~60 transitive dylibs, and the
      Tahoe `_CGLGetCurrentContext` landmine makes eager loading fragile).
      Revisit for the "any Mac" phase, together with an x86_64 build.
- [ ] **Bundle size**: 108 MB. PySide6's PyInstaller hook pulls in
      QtQml/QtQuick/QtPdf/QtNetwork/QtDBus frameworks the app never
      imports (via plugin dependencies), despite them being in the spec's
      `excludes`. Could be trimmed to ~60 MB by deleting frameworks
      post-build in `build_app.sh`; not worth the fragility yet.
- [ ] **Linux**: `tools.py` and `_mpv_bootstrap` already fall back to
      `PATH`/`find_library`; `make_icon.py --png` exists for a `.desktop`
      file; the spec's `BUNDLE` step is macOS-only. Untested.
- [ ] `stable`'s user-facing `README.md` still describes the from-source
      install only. At the next promotion, point it at `docs/INSTALL.md`
      (or copy that content in) — see `CLAUDE.md` > Branches for the
      merge procedure.

## UI / UX polish (DaVinci-Resolve-likeness)

- [x] Undo/redo now covers label/score add/rename/remove, the scoring
      toggle, and break/link continuation, in addition to cut edits.
- [ ] Undo/redo does **not** cover: Mark/Unmark Annotated, changing the
      videos/project directory, the subfolder toggle, theme. All are
      trivially re-doable by hand, so left out on purpose.
- [ ] Undo has no visible history (no "Undo <what>" menu text). The
      `Command` dataclass has no description field yet.

## Cross-video continuation follow-ups

- [x] Re-linking after the fact: "Link Continuation…" on a selected cut.
- [ ] Linking still only offers the *immediately previous* video's front
      halves (one hop, same as the banner). A cut can't be linked to a
      video two steps back, by design (`Project.pending_continuations()`).

## Correctness / robustness

- [x] Recursive/subfolder scanning: File > Include Subfolders.
- [x] Schema migration framework (`vat/migrations.py`): backup, one-step
      upgrades, refusal of newer files. No real migration exists yet;
      write the first one when a shape change actually happens, and add
      a test that loads a checked-in fixture of the old shape.
- [x] A project folder moved/copied by hand is re-homed on open
      (`ProjectStore.load`).
- [ ] `videos_dir` is still an absolute path in `project.json`; a project
      whose videos folder moves needs File > Change Videos Directory. A
      relative-to-project fallback would help synced-drive setups.

## Performance / non-functional requirements

- [x] **Measured** (2026-09-17, M3 Pro, synthetic 1280x720 H.264 test
      clip, `scripts/measure_footprint.py`-style sampling): RSS 290–350 MB
      while playing, CPU 30–40 % of one core during playback dropping to
      ~9 % paused. Well inside the <4 GB budget. **Not yet measured on
      the real 289-video project's footage** — run
      `.venv/bin/python scripts/measure_footprint.py --project <dir>
      --seconds 120` while stepping through it and note the peak here.
- [ ] Playback speed for sub-5-minute videos: exercised at 1x/0.5x/2x by
      hand; no dropped-frame measurement (mpv's `frame-drop-count`
      property could be observed and logged behind an env var).
- [ ] `Preloader` warms the OS page cache with a fixed 8MiB head-read; the
      "fetch a starting chunk, load the remainder after it's in the
      rendering region" requirement is satisfied by mpv's own bounded
      demuxer readahead rather than explicit chunked loading logic in our
      code. Revisit if real-world stutter is observed on large files.
- [x] Thumbnail extraction is prioritised by the visible playlist range
      and failed extractions are retried with backoff (30 s / 2 min /
      10 min) before being given up on for the session.
- [x] Waveform decoding is bounded to one worker, latest request wins.
- [ ] Waveform decode time on *long* videos is still unmeasured (a full
      audio-track decode per video). If it lags noticeably on hour-long
      footage, cache-warm the next video's waveform from `Preloader`.

## Verification (done by the agent this pass, with a real display)

The agent's shell now runs inside a real Aqua session, so the items that
previously read "please confirm by hand" were checked directly by
launching the app against a scratch project with real ffmpeg-generated
videos and reading screenshots:

- [x] Video renders **inside** the main window (Render API), not a
      separate OS window.
- [x] Timeline shows the correct total duration from `probe_duration()`
      on video switch, both cuts, the waveform strip, and a moving
      playhead; playlist rows get thumbnails; `.thumbnails/` and
      `.waveforms/` fill (ffmpeg works in-process, no `DYLD_*` leak).
- [x] Closing the window exits cleanly (exit code 0, mpv shut down, no
      hang). The earlier "self-terminates after ~15–20 s" mystery was the
      user closing the stray window: every instance received a
      *spontaneous* (window-system) `Close` event first, confirmed by
      instrumenting Qt and by asking.
- [x] The built `.app` launches under a Finder-like environment (minimal
      `PATH`, no `DYLD_*`), plays video, and resolves ffmpeg via
      `tools.py` (`vat --doctor` shows the resolution).
- [ ] **Still yours to check**: look/feel at your usual window size and
      on the real project (panel proportions, label colors), and the
      "Mark Annotated" click on the 289-video project now that thumbnails
      are prioritised/retried.

## Testing gaps

- [x] `playback/mpv_player.py` has direct tests against a fake `mpv`
      module (`tests/test_mpv_player.py`). Real libmpv playback remains
      manual-only by nature.
- [ ] No end-to-end test of the built bundle in CI beyond `--version`
      and `codesign --verify` (a GUI launch on a headless runner isn't
      meaningful). `packaging/README.md` describes the manual check.

## Explicitly out of scope (per REQUIREMENT.md)

- Actual video re-encoding / clip file generation — this tool only ever
  writes start/end/label mappings, never touches or exports raw video
  files. Don't add "export clip" functionality without checking back on
  this constraint.
