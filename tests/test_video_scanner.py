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
