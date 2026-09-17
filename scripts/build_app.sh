#!/usr/bin/env bash
# Build dist/VAT.app (+ a zip and its sha256) for the current machine's
# architecture. See packaging/README.md for the release process.
#
#   scripts/build_app.sh                 # ad-hoc signed (default)
#   VAT_SIGN_IDENTITY="Developer ID Application: Name (TEAMID)" \
#   VAT_NOTARY_PROFILE=vat-notary scripts/build_app.sh   # signed + notarized
#
# Env:
#   VENV                path to the venv to build with (default .venv)
#   VAT_SIGN_IDENTITY   codesign identity; unset/empty = ad-hoc ("-")
#   VAT_NOTARY_PROFILE  `xcrun notarytool store-credentials` profile name;
#                       unset = skip notarization
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VENV="${VENV:-.venv}"
PY="$VENV/bin/python"

if [ ! -x "$PY" ]; then
  echo "no venv at $VENV -- create one first: python3 -m venv .venv && .venv/bin/pip install -e '.[dev,build]'" >&2
  exit 1
fi

ARCH="$(uname -m)"
VERSION="$(PYTHONPATH=src "$PY" -c 'import vat; print(vat.__version__)')"
echo "==> Building VAT $VERSION for $ARCH with $("$PY" --version)"

echo "==> Installing build dependencies"
"$VENV/bin/pip" install -q -e ".[build]"

echo "==> Rendering icon"
"$PY" packaging/make_icon.py build/icon.icns

echo "==> Running PyInstaller"
rm -rf dist/VAT dist/VAT.app build/pyinstaller
"$VENV/bin/pyinstaller" --noconfirm --clean --distpath dist --workpath build/pyinstaller packaging/vat.spec
rm -rf dist/VAT  # the bare onedir folder; only the .app is shipped

APP="dist/VAT.app"
if [ -n "${VAT_SIGN_IDENTITY:-}" ]; then
  echo "==> Signing with '$VAT_SIGN_IDENTITY' (hardened runtime)"
  codesign --force --deep --options runtime --timestamp --sign "$VAT_SIGN_IDENTITY" "$APP"
else
  echo "==> Ad-hoc signing (no Developer ID: users must right-click > Open once, or install via the cask)"
  codesign --force --deep --sign - "$APP"
fi
codesign --verify --deep --strict "$APP"

ZIP="dist/VAT-$VERSION-$ARCH.zip"
rm -f "$ZIP"
if [ -n "${VAT_NOTARY_PROFILE:-}" ]; then
  echo "==> Notarizing via profile '$VAT_NOTARY_PROFILE'"
  ditto -c -k --keepParent "$APP" "$ZIP"
  xcrun notarytool submit "$ZIP" --keychain-profile "$VAT_NOTARY_PROFILE" --wait
  xcrun stapler staple "$APP"
  rm -f "$ZIP"
fi

echo "==> Zipping"
ditto -c -k --keepParent "$APP" "$ZIP"
SHA="$(shasum -a 256 "$ZIP" | cut -d' ' -f1)"
echo "$SHA  $(basename "$ZIP")" > "$ZIP.sha256"

echo
echo "Built:  $APP  ($(du -sh "$APP" | cut -f1))"
echo "Zip:    $ZIP  ($(du -sh "$ZIP" | cut -f1))"
echo "sha256: $SHA"
echo
echo "Smoke test:  $APP/Contents/MacOS/VAT --version"
