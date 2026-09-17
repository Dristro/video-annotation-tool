# Installing the Video Annotation Tool

Apple Silicon Mac, macOS 14 or newer.

## With Homebrew (recommended)

```bash
brew tap dristro/vat
brew install --cask vat
```

This installs `VAT.app` into `/Applications`, a `vat` command for the
Terminal, and the two tools video playback depends on (`mpv`, `ffmpeg`).

Because the app isn't signed with an Apple Developer ID yet, macOS may
refuse to open it the first time ("cannot verify the developer"). Either
right-click `VAT.app` in `/Applications` and choose **Open** (once is
enough), or install with `brew install --cask --no-quarantine vat`.

## Without Homebrew's cask

1. `brew install mpv ffmpeg` (Homebrew itself: https://brew.sh).
2. Download `VAT-<version>-arm64.zip` from the GitHub Releases page,
   unzip, drag `VAT.app` to `/Applications`.
3. First launch: right-click > Open.

## From source

```bash
brew install mpv ffmpeg
git clone https://github.com/Dristro/video-annotation-tool.git
cd video-annotation-tool && git checkout stable
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/vat
```

## Running

- Double-click `VAT.app`, or run `vat` (opens the last project) /
  `vat ~/path/to/project` from a Terminal.
- On first launch you're asked to create a project (a project directory
  for the annotation files, and a videos directory to annotate) or open
  an existing one.
- If `mpv`/`ffmpeg` are missing the app says so on startup and tells you
  the `brew install` command; it won't start without `mpv`, and runs
  without thumbnails/waveforms/durations if only `ffmpeg` is missing.

## Uninstalling

```bash
brew uninstall --cask vat          # keep settings
brew uninstall --zap --cask vat    # also remove ~/Library/Application Support/vat
```

Your projects (`project.json`, `annotations.json`, thumbnail caches)
live wherever you created them and are never touched by uninstalling.
