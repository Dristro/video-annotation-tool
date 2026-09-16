import pytest

from vat import app_settings


@pytest.fixture(autouse=True)
def isolated_settings_path(tmp_path, monkeypatch):
    # Never touch the real ~/Library/Application Support/vat/settings.json
    # from a test run.
    fake_path = tmp_path / "settings.json"
    monkeypatch.setattr(app_settings, "_settings_path", lambda: fake_path)
    return fake_path


def test_load_last_project_dir_none_when_missing() -> None:
    assert app_settings.load_last_project_dir() is None


def test_save_and_load_last_project_dir() -> None:
    app_settings.save_last_project_dir("/tmp/project-a")
    assert app_settings.load_last_project_dir() == "/tmp/project-a"


def test_recent_project_dirs_starts_empty() -> None:
    assert app_settings.load_recent_project_dirs() == []


def test_recent_project_dirs_most_recent_first() -> None:
    app_settings.save_last_project_dir("/tmp/a")
    app_settings.save_last_project_dir("/tmp/b")
    assert app_settings.load_recent_project_dirs() == ["/tmp/b", "/tmp/a"]


def test_reopening_a_project_moves_it_to_front_without_duplicating() -> None:
    app_settings.save_last_project_dir("/tmp/a")
    app_settings.save_last_project_dir("/tmp/b")
    app_settings.save_last_project_dir("/tmp/a")
    assert app_settings.load_recent_project_dirs() == ["/tmp/a", "/tmp/b"]


def test_recent_project_dirs_capped(monkeypatch) -> None:
    monkeypatch.setattr(app_settings, "MAX_RECENT_PROJECTS", 3)
    for i in range(5):
        app_settings.save_last_project_dir(f"/tmp/{i}")
    assert len(app_settings.load_recent_project_dirs()) == 3
    assert app_settings.load_recent_project_dirs() == ["/tmp/4", "/tmp/3", "/tmp/2"]


def test_load_theme_defaults_to_dark_when_missing() -> None:
    assert app_settings.load_theme() == "dark"


def test_save_and_load_theme() -> None:
    app_settings.save_theme("light")
    assert app_settings.load_theme() == "light"


def test_save_theme_does_not_clobber_other_settings() -> None:
    app_settings.save_last_project_dir("/tmp/project-a")
    app_settings.save_theme("light")
    assert app_settings.load_last_project_dir() == "/tmp/project-a"
    assert app_settings.load_theme() == "light"
