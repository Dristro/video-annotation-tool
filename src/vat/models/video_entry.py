from __future__ import annotations

from dataclasses import dataclass, field

from vat.models.cut import Cut


@dataclass
class VideoEntry:
    """The annotation mapping for a single video.

    Per REQUIREMENT.md: a video is "annotated" once it has an entry here, even
    if `cuts` is empty -- that only counts once the user explicitly confirms
    it via the "mark as annotated" action (see `annotated` flag).
    """

    annotated: bool = False
    cuts: list[Cut] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"annotated": self.annotated, "cuts": [c.to_dict() for c in self.cuts]}

    @classmethod
    def from_dict(cls, data: dict) -> "VideoEntry":
        return cls(
            annotated=bool(data.get("annotated", False)),
            cuts=[Cut.from_dict(c) for c in data.get("cuts", [])],
        )
