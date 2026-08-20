import pytest

from vat.annotations.annotation_store import AnnotationStore
from vat.errors import CutNotFoundError
from vat.models.cut import Cut


def test_new_video_not_annotated(tmp_project_dir):
    store = AnnotationStore.create(tmp_project_dir)
    assert store.is_annotated("a.mp4") is False
    assert store.get_entry("a.mp4") is None


def test_set_annotated_true_creates_empty_confirmed_entry(tmp_project_dir):
    store = AnnotationStore.create(tmp_project_dir)
    store.set_annotated("a.mp4", True)
    assert store.is_annotated("a.mp4") is True
    entry = store.get_entry("a.mp4")
    assert entry.cuts == []


def test_add_cut_creates_entry_but_not_annotated_until_confirmed(tmp_project_dir):
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0, label="goal"))
    # Per REQUIREMENT.md: having cuts alone doesn't mean "annotated" --
    # the user must explicitly confirm via the mark-annotated action.
    assert store.is_annotated("a.mp4") is False
    entry = store.get_entry("a.mp4")
    assert len(entry.cuts) == 1


def test_update_cut(tmp_project_dir):
    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut("a.mp4", Cut(start=1.0, end=2.0, label="goal"))
    store.update_cut("a.mp4", cut.id, start=1.5, label="foul")
    updated = store.get_entry("a.mp4").cuts[0]
    assert updated.start == 1.5
    assert updated.end == 2.0
    assert updated.label == "foul"


def test_update_missing_cut_raises(tmp_project_dir):
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0))
    with pytest.raises(CutNotFoundError):
        store.update_cut("a.mp4", "does-not-exist", start=0.0)


def test_remove_cut(tmp_project_dir):
    store = AnnotationStore.create(tmp_project_dir)
    cut = store.add_cut("a.mp4", Cut(start=1.0, end=2.0))
    store.remove_cut("a.mp4", cut.id)
    assert store.get_entry("a.mp4").cuts == []


def test_remove_missing_cut_raises(tmp_project_dir):
    store = AnnotationStore.create(tmp_project_dir)
    with pytest.raises(CutNotFoundError):
        store.remove_cut("a.mp4", "does-not-exist")


def test_rename_label_everywhere(tmp_project_dir):
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0, label="goal"))
    store.add_cut("b.mp4", Cut(start=3.0, end=4.0, label="goal"))
    store.add_cut("b.mp4", Cut(start=5.0, end=6.0, label="foul"))

    changed = store.rename_label_everywhere("goal", "goal-scored")

    assert changed == 2
    assert store.get_entry("a.mp4").cuts[0].label == "goal-scored"
    labels_in_b = {c.label for c in store.get_entry("b.mp4").cuts}
    assert labels_in_b == {"goal-scored", "foul"}


def test_persists_and_reloads(tmp_project_dir):
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0, label="goal"))
    store.set_annotated("a.mp4", True)

    reloaded = AnnotationStore.load(tmp_project_dir)
    assert reloaded.is_annotated("a.mp4") is True
    assert reloaded.get_entry("a.mp4").cuts[0].label == "goal"


def test_entry_absent_means_not_annotated(tmp_project_dir):
    store = AnnotationStore.create(tmp_project_dir)
    store.add_cut("a.mp4", Cut(start=1.0, end=2.0))
    # "b.mp4" was never touched at all -> no entry -> not annotated.
    assert store.get_entry("b.mp4") is None
    assert store.is_annotated("b.mp4") is False
