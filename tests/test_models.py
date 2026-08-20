import pytest

from vat.models.cut import Cut
from vat.models.label import Label
from vat.models.project_config import ProjectConfig
from vat.models.video_entry import VideoEntry


class TestLabel:
    def test_strips_whitespace(self):
        label = Label(name="  goal  ", shortcut=" g ")
        assert label.name == "goal"
        assert label.shortcut == "g"

    def test_rejects_empty_name(self):
        with pytest.raises(ValueError):
            Label(name="   ")

    def test_round_trip(self):
        label = Label(name="goal", shortcut="g", description="Ball crosses the line")
        assert Label.from_dict(label.to_dict()) == label

    def test_description_defaults_empty_and_strips(self):
        assert Label(name="goal").description == ""
        assert Label(name="goal", description="  scored  ").description == "scored"


class TestCut:
    def test_rejects_end_before_start(self):
        with pytest.raises(ValueError):
            Cut(start=10, end=5)

    def test_rejects_negative_times(self):
        with pytest.raises(ValueError):
            Cut(start=-1, end=5)

    def test_round_trip_preserves_id(self):
        cut = Cut(start=1.0, end=2.0, label="goal")
        restored = Cut.from_dict(cut.to_dict())
        assert restored.id == cut.id
        assert restored.start == cut.start
        assert restored.end == cut.end
        assert restored.label == cut.label

    def test_generates_unique_ids(self):
        a = Cut(start=0, end=1)
        b = Cut(start=0, end=1)
        assert a.id != b.id


class TestVideoEntry:
    def test_default_not_annotated_no_cuts(self):
        entry = VideoEntry()
        assert entry.annotated is False
        assert entry.cuts == []

    def test_round_trip(self):
        entry = VideoEntry(annotated=True, cuts=[Cut(start=0, end=1, label="x")])
        restored = VideoEntry.from_dict(entry.to_dict())
        assert restored.annotated is True
        assert len(restored.cuts) == 1
        assert restored.cuts[0].label == "x"


class TestProjectConfig:
    def test_find_label(self):
        config = ProjectConfig(
            project_dir="/tmp/p", videos_dir="/tmp/v", labels=[Label(name="goal", shortcut="g")]
        )
        assert config.find_label("goal") is not None
        assert config.find_label("missing") is None

    def test_round_trip(self):
        config = ProjectConfig(
            project_dir="/tmp/p", videos_dir="/tmp/v", labels=[Label(name="goal", shortcut="g")]
        )
        restored = ProjectConfig.from_dict(config.to_dict())
        assert restored.project_dir == config.project_dir
        assert restored.videos_dir == config.videos_dir
        assert restored.label_names() == ["goal"]
