import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_ROOT = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)


@pytest.fixture
def tmp_videos_dir(tmp_path):
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    for name in ("b.mp4", "a.mp4", "c.txt"):
        (videos_dir / name).write_bytes(b"not a real video, just bytes for scanning tests")
    return str(videos_dir)


@pytest.fixture
def tmp_project_dir(tmp_path):
    project_dir = tmp_path / "project"
    return str(project_dir)
