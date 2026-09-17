# Packaging and releasing

How the macOS `.app` is built and published. User-facing install steps
are in `docs/INSTALL.md`.

## What ships

`dist/VAT.app`, built by PyInstaller from `packaging/vat.spec`, contains
the Python runtime, the `vat` package, the Qt modules it imports, and
python-mpv's `mpv.py`. It does **not** contain libmpv, ffmpeg or ffprobe.
Those come from Homebrew (`brew install mpv ffmpeg`), exactly as for a
from-source install; the Homebrew cask declares them as dependencies so
`brew install --cask vat` pulls them in, and the app checks for them on
startup (`vat/runtime_deps.py`) and explains what to install if they're
missing rather than failing inside python-mpv's import.

Why not bundle them: Homebrew's libmpv pulls ~60 transitive dylibs, all
of which would need relinking (`install_name_tool`) into the bundle, and
this machine's OpenGL-symbol landmine (see `CLAUDE.md`) makes any eager
dylib loading fragile. Deferred until the "any Mac / Linux" phase.

Two runtime consequences the code already handles, and that a future
change must keep handling:

- A Finder-launched app gets launchd's minimal `PATH` (no
  `/opt/homebrew/bin`). Every subprocess goes through
  `vat/media/tools.py`, which also checks the Homebrew prefixes.
- `_mpv_bootstrap` loads `/opt/homebrew/lib/libmpv.dylib` explicitly,
  and scopes `DYLD_LIBRARY_PATH` to the `import mpv` line. PyInstaller's
  onedir bootloader (used here) does not set `DYLD_*` itself; if it ever
  does, thumbnails/waveforms/durations silently die -- `scripts/
  build_app.sh`'s smoke test doesn't catch that, opening a project in the
  built app and checking `.thumbnails/` fills does.

## Building locally

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev,build]"
scripts/build_app.sh            # -> dist/VAT.app, dist/VAT-<ver>-arm64.zip, .sha256
open dist/VAT.app               # or: dist/VAT.app/Contents/MacOS/VAT ~/some/project
```

The build is ad-hoc signed unless `VAT_SIGN_IDENTITY` is set (and
notarized only if `VAT_NOTARY_PROFILE` is too) -- see the header of
`scripts/build_app.sh`. The icon is drawn at build time by
`packaging/make_icon.py` (no binary asset checked in).

## Releasing

1. Bump `src/vat/__init__.py`'s `__version__`, update `CHANGELOG.md`
   (move `[Unreleased]` under the new version), commit on `main`.
2. Promote to `stable` when the user says so (`CLAUDE.md` > Branches).
3. Tag and push: `git tag v1.0.0 && git push origin v1.0.0`.
4. `.github/workflows/release.yml` builds on a `macos-15` (Apple
   Silicon) runner, runs the tests, attaches `VAT-<ver>-arm64.zip`, its
   `.sha256`, and a `vat.rb` with the sha filled in to a GitHub Release.
5. Copy that `vat.rb` into the tap repo (`Casks/vat.rb` in
   `github.com/Dristro/homebrew-vat`) and push. Users then get the new
   version with `brew upgrade --cask vat`.

### Creating the tap (one-time)

```bash
# A repo named exactly homebrew-vat under the GitHub user/org:
gh repo create Dristro/homebrew-vat --public --clone
cd homebrew-vat && mkdir Casks
cp ../video-annotation-tool/packaging/homebrew/Casks/vat.rb Casks/   # or the release's vat.rb
git add Casks/vat.rb && git commit -m "vat 1.0.0" && git push
brew tap dristro/vat && brew install --cask vat     # verify
```

`brew audit --cask vat` and `brew style dristro/vat` are worth running
in the tap before publishing.

## Code signing status

Ad-hoc only (no Apple Developer ID yet). Consequences, documented in the
cask's caveats and in `docs/INSTALL.md`: Gatekeeper blocks the first
launch of a downloaded copy with "cannot verify the developer"; users
right-click > Open once, or install with `--no-quarantine`. When a
Developer ID is available: store notarytool credentials
(`xcrun notarytool store-credentials vat-notary`), export
`VAT_SIGN_IDENTITY` and `VAT_NOTARY_PROFILE`, and `build_app.sh` does
the rest (hardened runtime, timestamp, notarize, staple).

## Linux (later)

PyInstaller works the same way there (`console=False` ELF + onedir);
`packaging/make_icon.py --png` produces a PNG for a `.desktop` file;
`vat/media/tools.py` and `_mpv_bootstrap` fall back to `PATH`/`find_library`
when the Homebrew paths don't exist. Nothing in the bundle is macOS-only
except `BUNDLE` in the spec.
