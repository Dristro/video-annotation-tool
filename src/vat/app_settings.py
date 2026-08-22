from __future__ import annotations

import json
from pathlib import Path

from vat.constants import APP_SETTINGS_FILENAME, APP_SUPPORT_DIR_NAME, MAX_RECENT_PROJECTS


def _settings_path() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_SUPPORT_DIR_NAME / APP_SETTINGS_FILENAME


def _load_settings() -> dict:
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_settings(data: dict) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def load_last_project_dir() -> str | None:
    return _load_settings().get("last_project_dir")


def load_recent_project_dirs() -> list[str]:
    return list(_load_settings().get("recent_project_dirs", []))


def load_theme() -> str:
    # A global (not per-project) preference on purpose -- the user asked
    # for it to persist across projects/sessions in the same place the
    # rest of this file already lives (~/Library/Application Support/vat/
    # settings.json), rather than in any single project's project.json.
    return _load_settings().get("theme", "dark")


def save_theme(theme: str) -> None:
    data = _load_settings()
    data["theme"] = theme
    _save_settings(data)


def save_last_project_dir(project_dir: str) -> None:
    # Merge into whatever's already on disk (read-modify-write) rather than
    # overwriting the whole file -- this is the one place a project is
    # recorded as opened, so it's also where the recent-projects MRU list
    # gets updated, and a blind overwrite would silently wipe that list
    # every time a project is opened/switched.
    data = _load_settings()
    data["last_project_dir"] = project_dir
    recent = [p for p in data.get("recent_project_dirs", []) if p != project_dir]
    recent.insert(0, project_dir)
    data["recent_project_dirs"] = recent[:MAX_RECENT_PROJECTS]
    _save_settings(data)
