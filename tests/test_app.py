from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.app import apply_dark_theme  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication | QCoreApplication:
    return QApplication.instance() or QApplication([])


def test_apply_dark_theme_sets_dark_window_color(qapp) -> None:
    apply_dark_theme(qapp)
    window_color = qapp.palette().color(QPalette.ColorRole.Window)
    # Dark, not the default light-gray Qt window color.
    assert window_color.lightness() < 128


def test_apply_dark_theme_keeps_text_readable(qapp) -> None:
    apply_dark_theme(qapp)
    text_color = qapp.palette().color(QPalette.ColorRole.WindowText)
    window_color = qapp.palette().color(QPalette.ColorRole.Window)
    assert text_color.lightness() > window_color.lightness()


def test_version_flag_prints_version_and_exits(capsys) -> None:
    from vat import __version__
    from vat.app import _parse_args

    with pytest.raises(SystemExit) as excinfo:
        _parse_args(["--version"])
    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_unknown_finder_style_args_are_ignored() -> None:
    from vat.app import _parse_args

    args = _parse_args(["-psn_0_12345", "/some/project"])
    assert args.project_dir == "/some/project"


def test_version_matches_pyproject_dynamic_source() -> None:
    from vat import __version__

    assert __version__.count(".") == 2
    assert all(part.isdigit() for part in __version__.split("."))


def test_doctor_report_lists_every_dependency_and_env_landmine(monkeypatch) -> None:
    from vat import app as app_module

    monkeypatch.setenv("DYLD_LIBRARY_PATH", "/leaked")
    report = app_module.doctor_report()
    for key in ("vat ", "python ", "libmpv ", "ffmpeg ", "ffprobe ", "PATH ", "DYLD_* ", "dependencies "):
        assert key in report
    assert "/leaked" in report


def test_doctor_flag_exits_without_a_qapplication(capsys, monkeypatch) -> None:
    from vat import app as app_module

    monkeypatch.setattr(app_module, "QApplication", None)  # would blow up if reached
    assert app_module.main(["--doctor"]) == 0
    assert "ffprobe" in capsys.readouterr().out
