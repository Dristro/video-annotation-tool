from __future__ import annotations

import json
from pathlib import Path

from vat.constants import APP_SETTINGS_FILENAME, APP_SUPPORT_DIR_NAME


def _settings_path() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_SUPPORT_DIR_NAME / APP_SETTINGS_FILENAME


def load_last_project_dir() -> str | None:
    path = _settings_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return data.get("last_project_dir")


def save_last_project_dir(project_dir: str) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_project_dir": project_dir}, indent=2))
