class VatError(Exception):
    """Base class for all application errors."""


class ProjectError(VatError):
    """Base class for project-related errors."""


class ProjectAlreadyExistsError(ProjectError):
    """Raised when creating a project in a directory that already holds one."""


class ProjectNotFoundError(ProjectError):
    """Raised when loading a project from a directory that has no project.json."""


class DuplicateLabelError(ProjectError):
    """Raised when adding a label whose name already exists in the project."""


class LabelNotFoundError(ProjectError):
    """Raised when referencing a label name that doesn't exist in the project."""


class DuplicateScoreDefinitionError(ProjectError):
    """Raised when adding a score definition whose name already exists in the project."""


class ScoreDefinitionNotFoundError(ProjectError):
    """Raised when referencing a score definition name that doesn't exist in the project."""


class CutNotFoundError(ProjectError):
    """Raised when referencing a cut id that doesn't exist for a video."""


class SchemaError(ProjectError):
    """Base class for project.json / annotations.json schema problems."""


class SchemaTooNewError(SchemaError):
    """Raised when a file was written by a newer version of the app than
    this one knows how to read. Deliberately not silently "best-effort"
    loaded: a newer schema may carry fields whose absence changes meaning,
    and rewriting the file from this version would destroy them.
    """


class MigrationError(SchemaError):
    """Raised when no migration path exists from a file's schema version
    to the current one (a gap in the migration registry)."""
