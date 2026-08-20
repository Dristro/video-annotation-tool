from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QDialog

from vat import app_settings
from vat.errors import ProjectNotFoundError
from vat.project.project import Project
from vat.ui.main_window import MainWindow
from vat.ui.project_dialog import ProjectDialog


def _load_startup_project() -> Project | None:
    last_dir = app_settings.load_last_project_dir()
    if last_dir:
        try:
            return Project.open(last_dir)
        except ProjectNotFoundError:
            pass
    return None


def main() -> int:
    app = QApplication(sys.argv)

    project = _load_startup_project()
    if project is None:
        dialog = ProjectDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.project is None:
            return 0
        project = dialog.project

    app_settings.save_last_project_dir(project.config.project_dir)

    window = MainWindow(project)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
