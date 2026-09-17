import pytest

from vat.annotations.annotation_store import AnnotationStore
from vat.errors import CutNotFoundError
from vat.models.cut import Cut


def test_new_video_not_annotated(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    assert store.is_annotated("a.mp4") is False
    assert store.get_entry("a.mp4") is None


def test_set_annotated_true_creates_empty_confirmed_entry(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    store.set_annotated("a.mp4", True)
    assert store.is_annotated("a.mp4") is True
    entry = store.get_entry("a.mp4")
    assert entry.cuts == []


def test_add_cut_creates_entry_but_not_annotated_until_confirmed(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0, label="goal"))
    # Per REQUIREMENT.md: having cuts alone doesn't mean "annotated" --
    # the user must explicitly confirm via the mark-annotated action.
    assert store.is_annotated("a.mp4") is False
    entry = store.get_entry("a.mp4")
    assert len(entry.cuts) == 1


def test_update_cut(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut("a.mp4", Cut(start=1.0, end=2.0, label="goal"))
    store.update_cut("a.mp4", cut.id, start=1.5, label="foul")
    updated = store.get_entry("a.mp4").cuts[0]
    assert updated.start == 1.5
    assert updated.end == 2.0
    assert updated.label == "foul"


def test_update_cut_without_scores_arg_preserves_existing_scores(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut("a.mp4", Cut(start=1.0, end=2.0, label="goal", scores={"Technique": 87.5}))
    # Updating start/label only -- must not silently wipe scores.
    store.update_cut("a.mp4", cut.id, start=1.5)
    updated = store.get_entry("a.mp4").cuts[0]
    assert updated.scores == {"Technique": 87.5}


def test_update_cut_can_replace_scores(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut("a.mp4", Cut(start=1.0, end=2.0, scores={"Technique": 50}))
    store.update_cut("a.mp4", cut.id, scores={"Technique": 75})
    assert store.get_entry("a.mp4").cuts[0].scores == {"Technique": 75}


def test_update_cut_preserves_continuation_fields(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut(
        "a.mp4",
        Cut(start=1.0, end=2.0, label="goal", continuation_id="abc123", continues_forward=True),
    )
    # Editing label/scores must not sever a continuation link -- only
    # explicit continuation-related mutations should ever change these.
    store.update_cut("a.mp4", cut.id, label="foul", scores={"Technique": 90})
    updated = store.get_entry("a.mp4").cuts[0]
    assert updated.continuation_id == "abc123"
    assert updated.continues_forward is True


def test_update_cut_without_justification_arg_preserves_existing_justification(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut("a.mp4", Cut(start=1.0, end=2.0, label="goal", justification="clear foul"))
    store.update_cut("a.mp4", cut.id, label="foul")
    assert store.get_entry("a.mp4").cuts[0].justification == "clear foul"


def test_update_cut_can_replace_justification(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut("a.mp4", Cut(start=1.0, end=2.0, justification="first draft"))
    store.update_cut("a.mp4", cut.id, justification="revised reasoning")
    assert store.get_entry("a.mp4").cuts[0].justification == "revised reasoning"


def test_update_cut_can_clear_justification_with_empty_string(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut("a.mp4", Cut(start=1.0, end=2.0, justification="no longer relevant"))
    store.update_cut("a.mp4", cut.id, justification="")
    assert store.get_entry("a.mp4").cuts[0].justification == ""


def test_break_continuation_preserves_justification(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut(
        "a.mp4",
        Cut(start=1.0, end=2.0, justification="why", continuation_id="abc123", continues_forward=True),
    )
    updated = store.break_continuation("a.mp4", cut.id)
    assert updated.justification == "why"


def test_break_continuation_clears_fields(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut(
        "a.mp4",
        Cut(start=1.0, end=2.0, label="goal", continuation_id="abc123", continues_forward=True),
    )
    updated = store.break_continuation("a.mp4", cut.id)
    assert updated.continuation_id is None
    assert updated.continues_forward is False
    # Everything else about the cut is untouched.
    assert updated.start == 1.0
    assert updated.end == 2.0
    assert updated.label == "goal"


def test_break_continuation_missing_cut_raises(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0))
    with pytest.raises(CutNotFoundError):
        store.break_continuation("a.mp4", "does-not-exist")


def test_update_missing_cut_raises(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0))
    with pytest.raises(CutNotFoundError):
        store.update_cut("a.mp4", "does-not-exist", start=0.0)


def test_remove_cut(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut("a.mp4", Cut(start=1.0, end=2.0))
    store.remove_cut("a.mp4", cut.id)
    assert store.get_entry("a.mp4").cuts == []


def test_remove_missing_cut_raises(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    with pytest.raises(CutNotFoundError):
        store.remove_cut("a.mp4", "does-not-exist")


def test_rename_label_everywhere(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0, label="goal"))
    store.add_cut("b.mp4", Cut(start=3.0, end=4.0, label="goal"))
    store.add_cut("b.mp4", Cut(start=5.0, end=6.0, label="foul"))

    changed = store.rename_label_everywhere("goal", "goal-scored")

    assert changed == 2
    assert store.get_entry("a.mp4").cuts[0].label == "goal-scored"
    labels_in_b = {c.label for c in store.get_entry("b.mp4").cuts}
    assert labels_in_b == {"goal-scored", "foul"}


def test_persists_and_reloads(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0, label="goal"))
    store.set_annotated("a.mp4", True)

    reloaded = AnnotationStore.load(tmp_project_dir)
    assert reloaded.is_annotated("a.mp4") is True
    assert reloaded.get_entry("a.mp4").cuts[0].label == "goal"


def test_entry_absent_means_not_annotated(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0))
    # "b.mp4" was never touched at all -> no entry -> not annotated.
    assert store.get_entry("b.mp4") is None
    assert store.is_annotated("b.mp4") is False


def test_rename_score_everywhere(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0, scores={"Technique": 80, "Confidence": 3}))
    store.add_cut("b.mp4", Cut(start=3.0, end=4.0, scores={"Technique": 60}))

    changed = store.rename_score_everywhere("Technique", "Skill")

    assert changed == 2
    assert store.get_entry("a.mp4").cuts[0].scores == {"Skill": 80, "Confidence": 3}
    assert store.get_entry("b.mp4").cuts[0].scores == {"Skill": 60}


def test_rename_score_everywhere_only_touches_matching_cuts(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0, scores={"Confidence": 3}))

    changed = store.rename_score_everywhere("Technique", "Skill")

    assert changed == 0
    assert store.get_entry("a.mp4").cuts[0].scores == {"Confidence": 3}


def test_scores_persist_and_reload(tmp_project_dir) -> None:
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0, scores={"Technique": 87.5}))

    reloaded = AnnotationStore.load(tmp_project_dir)
    assert reloaded.get_entry("a.mp4").cuts[0].scores == {"Technique": 87.5}


def test_set_continuation_overwrites_link_fields_and_optionally_end(tmp_project_dir) -> None:
    from vat.annotations.annotation_store import AnnotationStore
    from vat.models.cut import Cut

    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut("a.mp4", Cut(start=1.0, end=2.0, label="goal", scores={"T": 1.0}, justification="j"))

    linked = store.set_continuation("a.mp4", cut.id, "link1", True, end=99.0)
    assert (linked.continuation_id, linked.continues_forward, linked.end) == ("link1", True, 99.0)
    assert (linked.label, linked.scores, linked.justification, linked.start) == ("goal", {"T": 1.0}, "j", 1.0)

    relinked = store.set_continuation("a.mp4", cut.id, "link2", False)
    assert (relinked.continuation_id, relinked.continues_forward, relinked.end) == ("link2", False, 99.0)

    broken = store.break_continuation("a.mp4", cut.id)
    assert (broken.continuation_id, broken.continues_forward) == (None, False)

    reloaded = AnnotationStore.load(tmp_project_dir)
    assert reloaded.get_entry("a.mp4").cuts[0].end == 99.0


def test_remove_entry_if_empty_only_drops_cutless_entries(tmp_project_dir) -> None:
    from vat.annotations.annotation_store import AnnotationStore
    from vat.models.cut import Cut

    store = AnnotationStore.create(tmp_project_dir)
    assert store.remove_entry_if_empty("missing.mp4") is False
    store.set_annotated("empty.mp4", True)
    assert store.remove_entry_if_empty("empty.mp4") is True
    assert store.get_entry("empty.mp4") is None
    store.add_cut("full.mp4", Cut(start=0.0, end=1.0))
    assert store.remove_entry_if_empty("full.mp4") is False
    assert AnnotationStore.load(tmp_project_dir).get_entry("full.mp4") is not None
