from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class Cut:
    """A single start/end marker within a video, optionally tagged with a
    label name and optional named scores (e.g. {"Technique": 87.5}).

    The label and score names are stored as plain strings/keys (not
    foreign-key ids) so that the annotations file stays self-describing and
    readable on its own, per the requirement that the annotation file must
    be a public, portable artifact.
    """

    start: float
    end: float
    label: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < 0:
            raise ValueError("Cut start/end must be non-negative")
        if self.end < self.start:
            raise ValueError("Cut end must be >= start")
        self.label = self.label.strip()
        self.scores = dict(self.scores)  # defensive copy: don't alias the caller's dict

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start": self.start,
            "end": self.end,
            "label": self.label,
            "scores": dict(self.scores),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Cut":
        return cls(
            id=data.get("id", uuid.uuid4().hex),
            start=float(data["start"]),
            end=float(data["end"]),
            label=data.get("label", ""),
            scores=dict(data.get("scores", {})),
        )
