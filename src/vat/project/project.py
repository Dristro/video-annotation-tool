from __future__ import annotations

from pathlib import Path

from vat.annotations.annotation_store import AnnotationStore
from vat.media.video_scanner import VideoInfo, list_videos, rel_path_for
from vat.models.cut import Cut
from vat.models.label import Label
from vat.models.score_definition import ScoreDefinition
from vat.models.video_entry import VideoEntry
from vat.project.project_store import ProjectStore


class Project:
    """High-level facade combining the private project config and the public
    annotations mapping. This is the entry point the UI layer talks to so that
    operations spanning both files (like renaming a label) stay in sync.
    """

    def __init__(self, project_store: ProjectStore, annotation_store: AnnotationStore):
        self.project_store = project_store
        self.annotation_store = annotation_store

    # -- Lifecycle ------------------------------------------------------------
    @classmethod
    def create(cls, project_dir: str, videos_dir: str, labels: list[Label] | None = None) -> "Project":
        project_store = ProjectStore.create(project_dir, videos_dir, labels)
        annotation_store = AnnotationStore.create(project_store.config.project_dir)
        return cls(project_store, annotation_store)

    @classmethod
    def open(cls, project_dir: str) -> "Project":
        project_store = ProjectStore.load(project_dir)
        annotation_store = AnnotationStore.load(project_store.config.project_dir)
        return cls(project_store, annotation_store)

    @property
    def config(self):
        return self.project_store.config

    def set_videos_dir(self, videos_dir: str) -> None:
        self.project_store.set_videos_dir(videos_dir)

    def move_project_dir(self, new_project_dir: str) -> None:
        self.project_store.move_project_dir(new_project_dir)
        self.annotation_store = AnnotationStore.load(self.project_store.config.project_dir)

    # -- Videos ------------------------------------------------------------
    def list_videos(self) -> list[VideoInfo]:
        return list_videos(self.config.videos_dir)

    def rel_path(self, video_path: str) -> str:
        return rel_path_for(self.config.videos_dir, video_path)

    def is_annotated(self, rel_path: str) -> bool:
        return self.annotation_store.is_annotated(rel_path)

    def get_entry(self, rel_path: str) -> VideoEntry | None:
        return self.annotation_store.get_entry(rel_path)

    def set_annotated(self, rel_path: str, annotated: bool = True) -> None:
        self.annotation_store.set_annotated(rel_path, annotated)

    # -- Cuts ------------------------------------------------------------
    def add_cut(
        self, rel_path: str, start: float, end: float, label: str = "",
        scores: dict[str, float] | None = None,
        continuation_id: str | None = None, continues_forward: bool = False,
    ) -> Cut:
        return self.annotation_store.add_cut(
            rel_path,
            Cut(
                start=start, end=end, label=label, scores=dict(scores or {}),
                continuation_id=continuation_id, continues_forward=continues_forward,
            ),
        )

    def update_cut(self, rel_path: str, cut_id: str, **kwargs) -> Cut:
        return self.annotation_store.update_cut(rel_path, cut_id, **kwargs)

    def remove_cut(self, rel_path: str, cut_id: str) -> None:
        self.annotation_store.remove_cut(rel_path, cut_id)

    def is_cut_complete(self, cut: Cut) -> bool:
        """True unless scoring is enabled and the cut is missing a value for
        one of the project's *current* score definitions. Cuts created
        before a score was added, or before scoring was enabled at all,
        are flagged incomplete rather than silently accepted or blocked --
        nothing is retroactively enforced, this is purely informational.
        """
        if not self.config.scoring_enabled:
            return True
        return all(defn.name in cut.scores for defn in self.config.score_definitions)

    def missing_scores(self, cut: Cut) -> list[str]:
        if not self.config.scoring_enabled:
            return []
        return [defn.name for defn in self.config.score_definitions if defn.name not in cut.scores]

    def overlapping_cuts(self, rel_path: str, start: float, end: float, exclude_cut_id: str | None = None) -> list[Cut]:
        """Existing cuts in `rel_path` whose [start, end) range overlaps the
        given one. Overlaps are allowed (not rejected) per REQUIREMENT.md --
        this is purely so the UI can warn before creating/re-timing one,
        not a validation gate. `exclude_cut_id` excludes the cut being
        edited/re-timed from being reported as overlapping itself.
        """
        entry = self.get_entry(rel_path)
        if entry is None:
            return []
        return [
            cut
            for cut in entry.cuts
            if cut.id != exclude_cut_id and cut.start < end and start < cut.end
        ]

    def pending_continuation(self, rel_path: str, previous_rel_path: str | None) -> Cut | None:
        """If the previous video (by playlist order) has a cut marked
        `continues_forward` that this video hasn't yet completed with a
        matching `continuation_id`, return that front-half cut so the UI
        can offer to complete it. None otherwise (no previous video, no
        pending continuation, or it's already been completed).
        """
        if not previous_rel_path:
            return None
        previous_entry = self.get_entry(previous_rel_path)
        if previous_entry is None:
            return None
        current_entry = self.get_entry(rel_path)
        completed_ids = {
            c.continuation_id for c in (current_entry.cuts if current_entry else []) if c.continuation_id
        }
        for cut in previous_entry.cuts:
            if cut.continues_forward and cut.continuation_id and cut.continuation_id not in completed_ids:
                return cut
        return None

    # -- Labels ------------------------------------------------------------
    def add_label(self, name: str, shortcut: str = "", description: str = "") -> Label:
        return self.project_store.add_label(name, shortcut, description)

    def remove_labels(self, names: list[str]) -> None:
        self.project_store.remove_labels(names)

    def rename_label(
        self,
        old_name: str,
        new_name: str,
        new_shortcut: str | None = None,
        new_description: str | None = None,
    ) -> Label:
        label = self.project_store.rename_label(old_name, new_name, new_shortcut, new_description)
        if new_name != old_name:
            self.annotation_store.rename_label_everywhere(old_name, new_name)
        return label

    # -- Score definitions ---------------------------------------------------
    def set_scoring_enabled(self, enabled: bool) -> None:
        self.project_store.set_scoring_enabled(enabled)

    def add_score_definition(
        self, name: str, minimum: float = 0.0, maximum: float = 100.0, dtype: str = "float",
        description: str = "",
    ) -> ScoreDefinition:
        return self.project_store.add_score_definition(name, minimum, maximum, dtype, description)

    def remove_score_definitions(self, names: list[str]) -> None:
        self.project_store.remove_score_definitions(names)

    def rename_score_definition(
        self,
        old_name: str,
        new_name: str,
        new_minimum: float | None = None,
        new_maximum: float | None = None,
        new_dtype: str | None = None,
        new_description: str | None = None,
    ) -> ScoreDefinition:
        definition = self.project_store.rename_score_definition(
            old_name, new_name, new_minimum, new_maximum, new_dtype, new_description
        )
        if new_name != old_name:
            self.annotation_store.rename_score_everywhere(old_name, new_name)
        return definition
