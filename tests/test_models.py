import pytest

from vat.models.cut import Cut
from vat.models.label import Label
from vat.models.project_config import ProjectConfig
from vat.models.score_definition import ScoreDefinition
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

    def test_scores_default_empty(self):
        assert Cut(start=0, end=1).scores == {}

    def test_scores_round_trip(self):
        cut = Cut(start=1.0, end=2.0, label="goal", scores={"Technique": 87.5, "Confidence": 3})
        restored = Cut.from_dict(cut.to_dict())
        assert restored.scores == {"Technique": 87.5, "Confidence": 3}

    def test_scores_dict_is_independent_copy(self):
        original_scores = {"Technique": 50}
        cut = Cut(start=0, end=1, scores=original_scores)
        original_scores["Technique"] = 99  # mutate the caller's dict after construction
        assert cut.scores["Technique"] == 50  # cut must not alias it

    def test_generates_unique_ids(self):
        a = Cut(start=0, end=1)
        b = Cut(start=0, end=1)
        assert a.id != b.id

    def test_continuation_fields_default(self):
        cut = Cut(start=0, end=1)
        assert cut.continuation_id is None
        assert cut.continues_forward is False

    def test_continuation_fields_round_trip(self):
        cut = Cut(start=0, end=1, continuation_id="abc123", continues_forward=True)
        restored = Cut.from_dict(cut.to_dict())
        assert restored.continuation_id == "abc123"
        assert restored.continues_forward is True

    def test_continuation_fields_default_when_absent_from_dict(self):
        # Older annotations.json files predate these fields entirely.
        restored = Cut.from_dict({"id": "x", "start": 0, "end": 1, "label": ""})
        assert restored.continuation_id is None
        assert restored.continues_forward is False

    def test_justification_defaults_empty(self):
        assert Cut(start=0, end=1).justification == ""

    def test_justification_strips_whitespace(self):
        cut = Cut(start=0, end=1, justification="  because of X  ")
        assert cut.justification == "because of X"

    def test_justification_round_trip(self):
        cut = Cut(start=1.0, end=2.0, justification="Clear foul, hand ball.")
        restored = Cut.from_dict(cut.to_dict())
        assert restored.justification == "Clear foul, hand ball."

    def test_justification_default_when_absent_from_dict(self):
        # Older annotations.json files predate this field entirely.
        restored = Cut.from_dict({"id": "x", "start": 0, "end": 1, "label": ""})
        assert restored.justification == ""


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

    def test_scoring_disabled_by_default(self):
        config = ProjectConfig(project_dir="/tmp/p", videos_dir="/tmp/v")
        assert config.scoring_enabled is False
        assert config.score_definitions == []

    def test_find_score_definition(self):
        config = ProjectConfig(
            project_dir="/tmp/p",
            videos_dir="/tmp/v",
            scoring_enabled=True,
            score_definitions=[ScoreDefinition(name="Technique")],
        )
        assert config.find_score_definition("Technique") is not None
        assert config.find_score_definition("missing") is None

    def test_scoring_round_trip(self):
        config = ProjectConfig(
            project_dir="/tmp/p",
            videos_dir="/tmp/v",
            scoring_enabled=True,
            score_definitions=[ScoreDefinition(name="Confidence", minimum=1, maximum=5, dtype="int")],
        )
        restored = ProjectConfig.from_dict(config.to_dict())
        assert restored.scoring_enabled is True
        assert restored.score_definition_names() == ["Confidence"]
        assert restored.find_score_definition("Confidence").dtype == "int"
