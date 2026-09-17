# Homebrew cask for the Video Annotation Tool.
#
# Lives in this repo as the source of truth; the copy users install from
# is in the tap repo (github.com/Dristro/homebrew-vat, file Casks/vat.rb).
# The release workflow (.github/workflows/release.yml) emits a version of
# this file with the real sha256 filled in as a release asset -- copy that
# one into the tap after each release. See packaging/README.md.
#
#   brew tap dristro/vat
#   brew install --cask vat
#
cask "vat" do
  version "1.0.0"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000" # replaced per release

  url "https://github.com/Dristro/video-annotation-tool/releases/download/v#{version}/VAT-#{version}-arm64.zip"
  name "Video Annotation Tool"
  desc "Annotate videos with labeled cuts and scores without modifying the source files"
  homepage "https://github.com/Dristro/video-annotation-tool"

  livecheck do
    url :url
    strategy :github_latest
  end

  # Only Apple Silicon builds are published for now (the tool's target
  # machine); an Intel build would need the release workflow to run on an
  # x86_64 runner as well.
  depends_on arch: :arm64
  depends_on macos: ">= :sonoma"
  # Deliberately not bundled inside the .app (see packaging/README.md):
  # the app dlopen()s Homebrew's libmpv and shells out to ffmpeg/ffprobe.
  depends_on formula: "mpv"
  depends_on formula: "ffmpeg"

  app "VAT.app"
  # `vat` on the command line, like a from-source install:
  #   vat                      # open the last project
  #   vat ~/some/project       # open a specific project directory
  binary "#{appdir}/VAT.app/Contents/MacOS/VAT", target: "vat"

  zap trash: "~/Library/Application Support/vat"

  caveats <<~EOS
    VAT.app is signed ad-hoc, not with an Apple Developer ID. If macOS
    refuses to open it the first time, right-click the app in
    /Applications and choose Open (once), or reinstall with:

      brew reinstall --cask --no-quarantine vat

    Video playback uses Homebrew's mpv and ffmpeg, installed alongside.
  EOS
end
