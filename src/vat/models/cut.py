from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class Cut:
    """A single start/end marker within a video, optionally tagged with a label name.

    The label is stored as a plain string (not a foreign-key id) so that the
    annotations file stays self-describing and readable on its own, per the
    requirement that the annotation file must be a public, portable artifact.
    """

    start: float
    end: float
    label: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < 0:
            raise ValueError("Cut start/end must be non-negative")
        if self.end < self.start:
            raise ValueError("Cut end must be >= start")
        self.label = self.label.strip()

    def to_dict(self) -> dict:
        return {"id": self.id, "start": self.start, "end": self.end, "label": self.label}

    @classmethod
    def from_dict(cls, data: dict) -> "Cut":
        return cls(
            id=data.get("id", uuid.uuid4().hex),
            start=float(data["start"]),
            end=float(data["end"]),
            label=data.get("label", ""),
        )
