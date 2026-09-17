from vat import runtime_deps
from vat.media import tools


def test_everything_present_reports_ok(monkeypatch) -> None:
    monkeypatch.setattr(runtime_deps, "locate_libmpv", lambda: "/opt/homebrew/lib/libmpv.dylib")
    monkeypatch.setattr(runtime_deps, "find_tool", lambda name: f"/opt/homebrew/bin/{name}")

    report = runtime_deps.check_runtime_dependencies()

    assert report.ok
    assert report.missing_required == []
    assert report.missing_optional == []


def test_missing_libmpv_is_required(monkeypatch) -> None:
    monkeypatch.setattr(runtime_deps, "locate_libmpv", lambda: None)
    monkeypatch.setattr(runtime_deps, "find_tool", lambda name: f"/opt/homebrew/bin/{name}")

    report = runtime_deps.check_runtime_dependencies()

    assert not report.ok
    assert len(report.missing_required) == 1
    assert "mpv" in report.missing_required[0]
    assert "cannot start" in report.message()
    assert runtime_deps.INSTALL_HINT in report.message()


def test_missing_ffmpeg_tools_are_optional(monkeypatch) -> None:
    monkeypatch.setattr(runtime_deps, "locate_libmpv", lambda: "/opt/homebrew/lib/libmpv.dylib")
    monkeypatch.setattr(runtime_deps, "find_tool", lambda name: None)

    report = runtime_deps.check_runtime_dependencies()

    assert not report.ok
    assert report.missing_required == []
    assert report.missing_optional == ["ffmpeg", "ffprobe"]
    assert "thumbnails" in report.message()


def test_uses_the_shared_tool_resolver(monkeypatch) -> None:
    # Not a separate lookup: the same resolver the subprocess call sites
    # use, so the dialog and the actual behavior can't disagree.
    tools.clear_cache()
    seen = []
    monkeypatch.setattr(tools.shutil, "which", lambda name: seen.append(name) or "/x/" + name)
    monkeypatch.setattr(tools, "KNOWN_BIN_DIRS", ())
    monkeypatch.setattr(runtime_deps, "locate_libmpv", lambda: "/x/libmpv.dylib")
    try:
        runtime_deps.check_runtime_dependencies()
    finally:
        tools.clear_cache()
    assert seen == ["ffmpeg", "ffprobe"]
