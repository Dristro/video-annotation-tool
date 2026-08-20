from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from vat.models.label import Label

SCHEMA_VERSION = 1


@dataclass
class ProjectConfig:
    """Private project settings: where videos live, where project files live, and labels.

    Kept separate from the public annotations file so the annotations mapping
    can be shared/inspected without dragging along app-internal settings.
    """

    project_dir: str
    videos_dir: str
    labels: list[Label] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: int = SCHEMA_VERSION

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def label_names(self) -> list[str]:
        return [label.name for label in self.labels]

    def find_label(self, name: str) -> Label | None:
        for label in self.labels:
            if label.name == name:
                return label
        return None

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "project_dir": self.project_dir,
            "videos_dir": self.videos_dir,
            "labels": [label.to_dict() for label in self.labels],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectConfig":
        return cls(
            project_dir=data["project_dir"],
            videos_dir=data["videos_dir"],
            labels=[Label.from_dict(l) for l in data.get("labels", [])],
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )
