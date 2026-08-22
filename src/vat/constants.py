PROJECT_CONFIG_FILENAME = "project.json"
ANNOTATIONS_FILENAME = "annotations.json"

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}

# App-level (not project-level) settings, e.g. last opened project.
APP_SUPPORT_DIR_NAME = "vat"
APP_SETTINGS_FILENAME = "settings.json"
MAX_RECENT_PROJECTS = 8

# Cache dir names, nested under a project's own project_dir (not the
# videos_dir, which the user doesn't necessarily own write access to or
# want app-generated files mixed into).
THUMBNAILS_DIR_NAME = ".thumbnails"
WAVEFORMS_DIR_NAME = ".waveforms"
