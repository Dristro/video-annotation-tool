# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the macOS .app bundle. Driven by scripts/build_app.sh;
run directly with:  pyinstaller --noconfirm packaging/vat.spec

What is (and isn't) inside the bundle -- see packaging/README.md:

- Inside: the Python runtime, the `vat` package, PySide6 (only the Qt
  modules actually imported: Core/Gui/Widgets/OpenGL/OpenGLWidgets), and
  python-mpv's pure-Python `mpv.py`.
- NOT inside: libmpv, ffmpeg, ffprobe. They come from Homebrew at runtime,
  exactly as for a from-source install (`brew install mpv ffmpeg`), and
  the app checks for them on startup (vat/runtime_deps.py). Bundling them
  would mean relinking ~60 transitive dylibs and is deliberately deferred.
"""

import os
import sys

SRC = os.path.abspath(os.path.join(SPECPATH, "..", "src"))
sys.path.insert(0, SRC)
from vat import __version__  # noqa: E402  (single source of truth for the version)

ICON = os.environ.get("VAT_ICON", os.path.join(SPECPATH, "..", "build", "icon.icns"))
BUNDLE_ID = "com.dristro.vat"

a = Analysis(
    [os.path.join(SRC, "vat", "__main__.py")],
    pathex=[SRC],
    binaries=[],
    datas=[],
    hiddenimports=["mpv"],
    hookspath=[],
    runtime_hooks=[],
    # Qt modules PySide6's hook would otherwise happily drag in (hundreds of MB).
    excludes=[
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
        "PySide6.QtLocation", "PySide6.QtPositioning", "PySide6.QtBluetooth", "PySide6.QtNfc",
        "PySide6.QtSerialPort", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
        "PySide6.QtHelp", "PySide6.QtRemoteObjects", "PySide6.QtSensors", "PySide6.QtWebSockets",
        "PySide6.QtWebChannel", "PySide6.QtNetworkAuth", "PySide6.QtScxml", "PySide6.QtStateMachine",
        "PySide6.QtTextToSpeech", "PySide6.QtSpatialAudio", "PySide6.QtGraphs", "PySide6.QtHttpServer",
        "tkinter", "pytest", "PyInstaller",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VAT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app: no Terminal window when launched from Finder
    disable_windowed_traceback=False,
    argv_emulation=False,  # we parse argv ourselves (vat.app._parse_args)
    target_arch=None,  # whatever the building Python is (arm64 on Apple Silicon)
    codesign_identity=None,  # signing is done once, on the whole bundle, by build_app.sh
    entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="VAT")

app = BUNDLE(
    coll,
    name="VAT.app",
    icon=ICON if os.path.exists(ICON) else None,
    bundle_identifier=BUNDLE_ID,
    version=__version__,
    info_plist={
        "CFBundleName": "VAT",
        "CFBundleDisplayName": "Video Annotation Tool",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "LSMinimumSystemVersion": "14.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,  # follow the system light/dark setting
        "LSApplicationCategoryType": "public.app-category.video",
        "NSHumanReadableCopyright": "MIT License",
    },
)
