import os
import stat

import pytest

from vat.media import tools


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    tools.clear_cache()
    yield
    tools.clear_cache()


def _make_executable(path) -> str:
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def test_env_override_wins_over_path(tmp_path, monkeypatch) -> None:
    override = _make_executable(tmp_path / "my-ffmpeg")
    monkeypatch.setenv("VAT_FFMPEG", override)
    monkeypatch.setattr(tools.shutil, "which", lambda name: "/usr/bin/ffmpeg")

    assert tools.find_tool("ffmpeg") == override


def test_env_override_is_ignored_when_not_executable(tmp_path, monkeypatch) -> None:
    bogus = tmp_path / "not-there"
    monkeypatch.setenv("VAT_FFMPEG", str(bogus))
    monkeypatch.setattr(tools.shutil, "which", lambda name: "/usr/bin/ffmpeg")

    assert tools.find_tool("ffmpeg") == "/usr/bin/ffmpeg"


def test_falls_back_to_known_homebrew_dirs_when_not_on_path(tmp_path, monkeypatch) -> None:
    # The Finder-launched .app case: PATH is launchd's minimal default, so
    # shutil.which() finds nothing, but Homebrew's bin dir still has it.
    monkeypatch.delenv("VAT_FFPROBE", raising=False)
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    brew_bin = tmp_path / "opt" / "homebrew" / "bin"
    brew_bin.mkdir(parents=True)
    ffprobe = _make_executable(brew_bin / "ffprobe")
    monkeypatch.setattr(tools, "KNOWN_BIN_DIRS", (str(brew_bin),))

    assert tools.find_tool("ffprobe") == ffprobe


def test_missing_tool_returns_none_and_tool_path_returns_bare_name(monkeypatch) -> None:
    monkeypatch.delenv("VAT_NOPE", raising=False)
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    monkeypatch.setattr(tools, "KNOWN_BIN_DIRS", ())

    assert tools.find_tool("nope") is None
    assert tools.tool_path("nope") == "nope"  # subprocess.run() then raises FileNotFoundError, as before


def test_result_is_cached_until_cleared(monkeypatch) -> None:
    calls = []
    monkeypatch.delenv("VAT_FFMPEG", raising=False)
    monkeypatch.setattr(tools.shutil, "which", lambda name: calls.append(name) or "/x/ffmpeg")

    tools.find_tool("ffmpeg")
    tools.find_tool("ffmpeg")
    assert calls == ["ffmpeg"]

    tools.clear_cache()
    tools.find_tool("ffmpeg")
    assert calls == ["ffmpeg", "ffmpeg"]


@pytest.mark.skipif(not os.path.exists("/opt/homebrew/bin/ffmpeg"), reason="Homebrew ffmpeg not installed here")
def test_real_homebrew_ffmpeg_is_found_even_with_an_empty_path(monkeypatch) -> None:
    monkeypatch.delenv("VAT_FFMPEG", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    assert tools.find_tool("ffmpeg") == "/opt/homebrew/bin/ffmpeg"
