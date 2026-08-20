from __future__ import annotations

from pathlib import Path

from vat.annotations.annotation_store import AnnotationStore
from vat.media.video_scanner import VideoInfo, list_videos, rel_path_for
from vat.models.cut import Cut
from vat.models.label import Label
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
    def add_cut(self, rel_path: str, start: float, end: float, label: str = "") -> Cut:
        return self.annotation_store.add_cut(rel_path, Cut(start=start, end=end, label=label))

    def update_cut(self, rel_path: str, cut_id: str, **kwargs) -> Cut:
        return self.annotation_store.update_cut(rel_path, cut_id, **kwargs)

    def remove_cut(self, rel_path: str, cut_id: str) -> None:
        self.annotation_store.remove_cut(rel_path, cut_id)

    # -- Labels ------------------------------------------------------------
    def add_label(self, name: str, shortcut: str = "") -> Label:
        return self.project_store.add_label(name, shortcut)

    def remove_labels(self, names: list[str]) -> None:
        self.project_store.remove_labels(names)

    def rename_label(self, old_name: str, new_name: str, new_shortcut: str | None = None) -> Label:
        label = self.project_store.rename_label(old_name, new_name, new_shortcut)
        if new_name != old_name:
            self.annotation_store.rename_label_everywhere(old_name, new_name)
        return label
