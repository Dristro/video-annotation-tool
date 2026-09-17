from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from vat.models.label import Label
from vat.models.score_definition import ScoreDefinition

SCHEMA_VERSION = 1


@dataclass
class ProjectConfig:
    """Private project settings: where videos live, where project files live,
    labels, and (optionally) named per-cut scores.

    Kept separate from the public annotations file so the annotations mapping
    can be shared/inspected without dragging along app-internal settings.
    """

    project_dir: str
    videos_dir: str
    labels: list[Label] = field(default_factory=list)
    scoring_enabled: bool = False
    score_definitions: list[ScoreDefinition] = field(default_factory=list)
    # Whether list_videos() walks subfolders of videos_dir (off by default:
    # a flat playlist). Additive with a default, so no schema bump needed.
    recursive_scan: bool = False
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

    def score_definition_names(self) -> list[str]:
        return [defn.name for defn in self.score_definitions]

    def find_score_definition(self, name: str) -> ScoreDefinition | None:
        for defn in self.score_definitions:
            if defn.name == name:
                return defn
        return None

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "project_dir": self.project_dir,
            "videos_dir": self.videos_dir,
            "labels": [label.to_dict() for label in self.labels],
            "scoring_enabled": self.scoring_enabled,
            "score_definitions": [defn.to_dict() for defn in self.score_definitions],
            "recursive_scan": self.recursive_scan,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectConfig":
        return cls(
            project_dir=data["project_dir"],
            videos_dir=data["videos_dir"],
            labels=[Label.from_dict(l) for l in data.get("labels", [])],
            scoring_enabled=data.get("scoring_enabled", False),
            score_definitions=[ScoreDefinition.from_dict(d) for d in data.get("score_definitions", [])],
            recursive_scan=bool(data.get("recursive_scan", False)),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )
