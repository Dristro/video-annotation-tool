"""Schema versioning for the two on-disk files (`project.json`,
`annotations.json`).

Both files carry a top-level `schema_version` integer. Every shape change
that isn't purely additive-with-a-default (a renamed key, a changed
meaning, a restructured nesting) must bump the file's current version and
register a one-step migration here; additive fields with sensible
`from_dict` defaults do *not* need one (that's how `justification` and
the continuation fields were added under version 1).

How a load works (`upgrade()`):

1. A file with no `schema_version` at all is treated as version 1 -- the
   original shape, which always wrote the field, so this only matters for
   hand-edited files.
2. A version *newer* than this build knows raises `SchemaTooNewError`
   rather than loading best-effort: silently rewriting a newer file from
   an older app would drop whatever the newer fields were.
3. An older version is migrated one step at a time through the registry
   (`1 -> 2`, `2 -> 3`, ...). A gap raises `MigrationError`.
4. Before anything is rewritten, the original file is copied to
   `<name>.v<old-version>.bak` next to it (never overwritten if it
   already exists, so the *oldest* pre-migration copy survives repeated
   attempts). `annotations.json` is the user's actual work product; a
   migration bug must never be the only copy's undoing.

The store then saves the migrated data back at the current version, so
the file on disk is upgraded exactly once.

Registries are plain dicts keyed by *from*-version so tests can register
synthetic steps with `monkeypatch`. There are no real migrations yet:
both files are still at version 1.
"""

from __future__ import annotations

import copy
import shutil
from pathlib import Path
from typing import Callable

from vat.errors import MigrationError, SchemaTooNewError

Migration = Callable[[dict], dict]

# from-version -> function returning the data as the next version.
PROJECT_MIGRATIONS: dict[int, Migration] = {}
ANNOTATION_MIGRATIONS: dict[int, Migration] = {}


def upgrade(
    data: dict, path: Path, current_version: int, migrations: dict[int, Migration], kind: str,
) -> tuple[dict, bool]:
    """Return `(data at current_version, whether anything changed)`.

    `path` is only used to write the pre-migration backup; the caller is
    responsible for saving the returned data.
    """
    version = int(data.get("schema_version", 1))
    if version == current_version:
        return data, False
    if version > current_version:
        raise SchemaTooNewError(
            f"{path.name} is schema version {version}, but this version of the app only understands "
            f"up to version {current_version}. Please update the app to open this {kind}."
        )
    _write_backup(path, version)
    migrated = copy.deepcopy(data)
    while version < current_version:
        step = migrations.get(version)
        if step is None:
            raise MigrationError(
                f"No migration registered from {path.name} schema version {version} to {version + 1}."
            )
        migrated = step(migrated)
        version += 1
        migrated["schema_version"] = version
    return migrated, True


def backup_path(path: Path, version: int) -> Path:
    return path.with_name(f"{path.name}.v{version}.bak")


def _write_backup(path: Path, version: int) -> None:
    if not path.exists():
        return
    target = backup_path(path, version)
    if target.exists():
        return  # keep the oldest pre-migration copy, don't clobber it
    shutil.copy2(path, target)
