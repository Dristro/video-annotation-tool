import os

from vat.media.video_scanner import list_videos, rel_path_for


def test_list_videos_filters_extensions_and_sorts(tmp_videos_dir) -> None:
    videos = list_videos(tmp_videos_dir)
    names = [v.rel_path for v in videos]
    assert names == ["a.mp4", "b.mp4"]  # c.txt excluded, sorted alphabetically


def test_list_videos_missing_dir_returns_empty(tmp_path) -> None:
    assert list_videos(str(tmp_path / "does-not-exist")) == []


def test_rel_path_for(tmp_videos_dir) -> None:
    video_path = os.path.join(tmp_videos_dir, "a.mp4")
    assert rel_path_for(tmp_videos_dir, video_path) == "a.mp4"


def _touch(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"bytes")


def test_flat_scan_ignores_subfolders_by_default(tmp_path) -> None:
    _touch(tmp_path / "top.mp4")
    _touch(tmp_path / "sub" / "nested.mp4")
    assert [v.rel_path for v in list_videos(str(tmp_path))] == ["top.mp4"]


def test_recursive_scan_walks_subfolders_with_posix_rel_paths(tmp_path) -> None:
    _touch(tmp_path / "top.mp4")
    _touch(tmp_path / "day2" / "cam1" / "b.mov")
    _touch(tmp_path / "day1" / "a.mp4")
    _touch(tmp_path / "day1" / "notes.txt")

    videos = list_videos(str(tmp_path), recursive=True)

    assert [v.rel_path for v in videos] == ["day1/a.mp4", "day2/cam1/b.mov", "top.mp4"]
    assert videos[0].path == str(tmp_path / "day1" / "a.mp4")


def test_scan_skips_hidden_files_and_directories(tmp_path) -> None:
    _touch(tmp_path / ".hidden.mp4")
    _touch(tmp_path / ".cache" / "thumb.mp4")
    _touch(tmp_path / "visible.mp4")
    assert [v.rel_path for v in list_videos(str(tmp_path), recursive=True)] == ["visible.mp4"]
    assert [v.rel_path for v in list_videos(str(tmp_path))] == ["visible.mp4"]


def test_rel_path_for_nested_video_matches_recursive_listing(tmp_path) -> None:
    _touch(tmp_path / "day1" / "a.mp4")
    listed = list_videos(str(tmp_path), recursive=True)[0]
    assert rel_path_for(str(tmp_path), listed.path) == "day1/a.mp4" == listed.rel_path
