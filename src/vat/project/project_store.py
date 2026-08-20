from __future__ import annotations

import json
import shutil
from pathlib import Path

from vat.constants import PROJECT_CONFIG_FILENAME
from vat.models.label import Label
from vat.models.project_config import ProjectConfig
from vat.errors import (
    DuplicateLabelError,
    LabelNotFoundError,
    ProjectAlreadyExistsError,
    ProjectNotFoundError,
)


class ProjectStore:
    """Reads/writes the private `project.json` config file for a project directory."""

    def __init__(self, config: ProjectConfig):
        self.config = config

    @property
    def config_path(self) -> Path:
        return Path(self.config.project_dir) / PROJECT_CONFIG_FILENAME

    @classmethod
    def create(cls, project_dir: str, videos_dir: str, labels: list[Label] | None = None) -> "ProjectStore":
        project_path = Path(project_dir)
        if (project_path / PROJECT_CONFIG_FILENAME).exists():
            raise ProjectAlreadyExistsError(f"A project already exists at {project_dir}")
        project_path.mkdir(parents=True, exist_ok=True)
        config = ProjectConfig(
            project_dir=str(project_path.resolve()),
            videos_dir=str(Path(videos_dir).resolve()),
            labels=list(labels or []),
        )
        store = cls(config)
        store.save()
        return store

    @classmethod
    def load(cls, project_dir: str) -> "ProjectStore":
        config_path = Path(project_dir) / PROJECT_CONFIG_FILENAME
        if not config_path.exists():
            raise ProjectNotFoundError(f"No project.json found in {project_dir}")
        data = json.loads(config_path.read_text())
        config = ProjectConfig.from_dict(data)
        return cls(config)

    def save(self) -> None:
        self.config.touch()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self.config.to_dict(), indent=2))

    def set_videos_dir(self, videos_dir: str) -> None:
        self.config.videos_dir = str(Path(videos_dir).resolve())
        self.save()

    def move_project_dir(self, new_project_dir: str) -> None:
        """Move the whole project directory (config + annotations + any cache) to a new path."""
        old_path = Path(self.config.project_dir).resolve()
        new_path = Path(new_project_dir).resolve()
        if old_path == new_path:
            return
        if new_path.exists() and any(new_path.iterdir()):
            raise ProjectAlreadyExistsError(f"Target directory {new_path} is not empty")
        new_path.parent.mkdir(parents=True, exist_ok=True)
        if new_path.exists():
            new_path.rmdir()
        shutil.move(str(old_path), str(new_path))
        self.config.project_dir = str(new_path)
        self.save()

    # -- Label management -------------------------------------------------
    def add_label(self, name: str, shortcut: str = "") -> Label:
        if self.config.find_label(name) is not None:
            raise DuplicateLabelError(f"Label '{name}' already exists")
        label = Label(name=name, shortcut=shortcut)
        self.config.labels.append(label)
        self.save()
        return label

    def remove_labels(self, names: list[str]) -> None:
        name_set = set(names)
        self.config.labels = [l for l in self.config.labels if l.name not in name_set]
        self.save()

    def rename_label(self, old_name: str, new_name: str, new_shortcut: str | None = None) -> Label:
        label = self.config.find_label(old_name)
        if label is None:
            raise LabelNotFoundError(f"Label '{old_name}' not found")
        new_name = new_name.strip()
        if new_name != old_name and self.config.find_label(new_name) is not None:
            raise DuplicateLabelError(f"Label '{new_name}' already exists")
        label.name = new_name
        if new_shortcut is not None:
            label.shortcut = new_shortcut.strip()
        self.save()
        return label
