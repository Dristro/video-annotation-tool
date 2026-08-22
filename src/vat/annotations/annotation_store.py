from __future__ import annotations

import json
from pathlib import Path

from vat.constants import ANNOTATIONS_FILENAME
from vat.models.cut import Cut
from vat.models.video_entry import VideoEntry
from vat.errors import CutNotFoundError

SCHEMA_VERSION = 1


class AnnotationStore:
    """Reads/writes the public `annotations.json` file: video path -> cuts + annotated flag.

    This file is intentionally self-contained (labels stored as plain strings)
    so it can be read and understood without the private project.json.
    """

    def __init__(self, path: Path, videos: dict[str, VideoEntry] | None = None):
        self.path = Path(path)
        self.videos: dict[str, VideoEntry] = videos or {}

    @classmethod
    def create(cls, project_dir: str) -> "AnnotationStore":
        path = Path(project_dir) / ANNOTATIONS_FILENAME
        store = cls(path, {})
        store.save()
        return store

    @classmethod
    def load(cls, project_dir: str) -> "AnnotationStore":
        path = Path(project_dir) / ANNOTATIONS_FILENAME
        if not path.exists():
            return cls.create(project_dir)
        data = json.loads(path.read_text())
        videos = {
            rel_path: VideoEntry.from_dict(entry_data)
            for rel_path, entry_data in data.get("videos", {}).items()
        }
        return cls(path, videos)

    def save(self) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "videos": {rel_path: entry.to_dict() for rel_path, entry in self.videos.items()},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2))

    # -- Queries ------------------------------------------------------------
    def get_entry(self, rel_path: str) -> VideoEntry | None:
        return self.videos.get(rel_path)

    def is_annotated(self, rel_path: str) -> bool:
        entry = self.videos.get(rel_path)
        return bool(entry and entry.annotated)

    # -- Mutations ------------------------------------------------------------
    def _entry(self, rel_path: str) -> VideoEntry:
        return self.videos.setdefault(rel_path, VideoEntry())

    def set_annotated(self, rel_path: str, annotated: bool = True) -> None:
        entry = self._entry(rel_path)
        entry.annotated = annotated
        self.save()

    def add_cut(self, rel_path: str, cut: Cut) -> Cut:
        entry = self._entry(rel_path)
        entry.cuts.append(cut)
        self.save()
        return cut

    def update_cut(self, rel_path: str, cut_id: str, start: float | None = None,
                    end: float | None = None, label: str | None = None,
                    scores: dict[str, float] | None = None,
                    justification: str | None = None) -> Cut:
        entry = self.videos.get(rel_path)
        if entry is None:
            raise CutNotFoundError(f"No entry for video '{rel_path}'")
        for cut in entry.cuts:
            if cut.id == cut_id:
                new_start = cut.start if start is None else start
                new_end = cut.end if end is None else end
                new_label = cut.label if label is None else label
                # None means "leave scores untouched", not "clear them" --
                # only replace when a scores dict is explicitly passed.
                new_scores = dict(cut.scores) if scores is None else dict(scores)
                # Same None-means-unchanged convention as label -- an
                # explicit "" does clear it (justification is optional, so
                # clearing it back to empty is a legitimate edit).
                new_justification = cut.justification if justification is None else justification
                # continuation_id/continues_forward aren't editable through
                # this method (no caller passes them) -- carry them over
                # from the existing cut rather than letting the Cut()
                # constructor reset them to their dataclass defaults, which
                # would silently sever a continuation link on any edit.
                updated = Cut(
                    id=cut.id, start=new_start, end=new_end, label=new_label, scores=new_scores,
                    justification=new_justification,
                    continuation_id=cut.continuation_id, continues_forward=cut.continues_forward,
                )
                entry.cuts[entry.cuts.index(cut)] = updated
                self.save()
                return updated
        raise CutNotFoundError(f"No cut '{cut_id}' for video '{rel_path}'")

    def break_continuation(self, rel_path: str, cut_id: str) -> Cut:
        """Clear a cut's continuation_id/continues_forward, severing it
        from whatever cut it was linked to. A dedicated method rather than
        going through update_cut(), which deliberately never touches these
        fields (see its docstring) -- explicitly breaking a link is a
        distinct action from an ordinary label/score/timing edit. The
        dangling id left on the other half of the pair (if any) is
        harmless per BACKLOG.md -- it just won't match anything anymore.
        """
        entry = self.videos.get(rel_path)
        if entry is None:
            raise CutNotFoundError(f"No entry for video '{rel_path}'")
        for cut in entry.cuts:
            if cut.id == cut_id:
                updated = Cut(
                    id=cut.id, start=cut.start, end=cut.end, label=cut.label, scores=dict(cut.scores),
                    justification=cut.justification,
                    continuation_id=None, continues_forward=False,
                )
                entry.cuts[entry.cuts.index(cut)] = updated
                self.save()
                return updated
        raise CutNotFoundError(f"No cut '{cut_id}' for video '{rel_path}'")

    def remove_cut(self, rel_path: str, cut_id: str) -> None:
        entry = self.videos.get(rel_path)
        if entry is None:
            raise CutNotFoundError(f"No entry for video '{rel_path}'")
        before = len(entry.cuts)
        entry.cuts = [c for c in entry.cuts if c.id != cut_id]
        if len(entry.cuts) == before:
            raise CutNotFoundError(f"No cut '{cut_id}' for video '{rel_path}'")
        self.save()

    def rename_label_everywhere(self, old_name: str, new_name: str) -> int:
        """Rename every cut using `old_name` to `new_name`. Returns count of cuts changed."""
        changed = 0
        for entry in self.videos.values():
            for cut in entry.cuts:
                if cut.label == old_name:
                    cut.label = new_name
                    changed += 1
        if changed:
            self.save()
        return changed

    def rename_score_everywhere(self, old_name: str, new_name: str) -> int:
        """Rename the `old_name` key to `new_name` in every cut's scores dict.

        Returns the count of cuts changed.
        """
        changed = 0
        for entry in self.videos.values():
            for cut in entry.cuts:
                if old_name in cut.scores:
                    cut.scores[new_name] = cut.scores.pop(old_name)
                    changed += 1
        if changed:
            self.save()
        return changed
