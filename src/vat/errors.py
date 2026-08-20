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


class CutNotFoundError(ProjectError):
    """Raised when referencing a cut id that doesn't exist for a video."""
