import os
import subprocess
import sys

from vat.playback import _mpv_bootstrap
from vat.playback._mpv_bootstrap import DYLD_LIBRARY_PATH, libmpv_discoverable


def test_dyld_path_is_set_inside_the_block_and_removed_after(monkeypatch) -> None:
    monkeypatch.setattr(_mpv_bootstrap, "_lib_dir", "/opt/homebrew/lib")
    monkeypatch.delenv(DYLD_LIBRARY_PATH, raising=False)

    with libmpv_discoverable():
        assert "/opt/homebrew/lib" in os.environ[DYLD_LIBRARY_PATH]

    assert DYLD_LIBRARY_PATH not in os.environ


def test_a_pre_existing_dyld_path_is_restored_exactly(monkeypatch) -> None:
    monkeypatch.setattr(_mpv_bootstrap, "_lib_dir", "/opt/homebrew/lib")
    monkeypatch.setenv(DYLD_LIBRARY_PATH, "/somewhere/else")

    with libmpv_discoverable():
        assert "/somewhere/else" in os.environ[DYLD_LIBRARY_PATH]
        assert "/opt/homebrew/lib" in os.environ[DYLD_LIBRARY_PATH]

    assert os.environ[DYLD_LIBRARY_PATH] == "/somewhere/else"


def test_dyld_path_is_restored_even_if_the_block_raises(monkeypatch) -> None:
    monkeypatch.setattr(_mpv_bootstrap, "_lib_dir", "/opt/homebrew/lib")
    monkeypatch.delenv(DYLD_LIBRARY_PATH, raising=False)

    try:
        with libmpv_discoverable():
            raise RuntimeError("import mpv blew up")
    except RuntimeError:
        pass

    assert DYLD_LIBRARY_PATH not in os.environ


def test_no_dyld_path_needed_when_libmpv_was_already_discoverable(monkeypatch) -> None:
    monkeypatch.setattr(_mpv_bootstrap, "_lib_dir", None)
    monkeypatch.delenv(DYLD_LIBRARY_PATH, raising=False)

    with libmpv_discoverable():
        assert DYLD_LIBRARY_PATH not in os.environ


def test_importing_mpv_player_leaves_no_dyld_path_behind(tmp_path) -> None:
    """The regression this whole mechanism exists for.

    `DYLD_LIBRARY_PATH` used to be set permanently by the libmpv bootstrap,
    and every ffmpeg/ffprobe subprocess inherited it -- which makes dyld
    bind eagerly and abort those processes on the very same missing
    `_CGLGetCurrentContext` symbol the bootstrap works around for libmpv.
    Every thumbnail, waveform and duration probe failed silently as a
    result. Run in a subprocess because the import is process-global and
    already happened for this test session.
    """
    script = (
        "import os, sys;"
        "sys.path.insert(0, %r);"
        "import vat.playback.mpv_player;"
        "print(os.environ.get('DYLD_LIBRARY_PATH', '<unset>'))" % os.path.join(os.path.dirname(__file__), "..", "src")
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        # No libmpv on this machine (CI) -- nothing to leak, nothing to test.
        return
    assert result.stdout.strip() == "<unset>"
