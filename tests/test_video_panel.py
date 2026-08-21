import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.ui.video_panel import DEFAULT_SPEED_INDEX, SPEED_STEPS, VideoPanel, format_time  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(qapp):
    return VideoPanel()


class TestFormatTime:
    def test_seconds_only(self):
        assert format_time(5) == "0:05"

    def test_minutes_and_seconds(self):
        assert format_time(125) == "2:05"

    def test_hours(self):
        assert format_time(3725) == "1:02:05"

    def test_negative_clamped_to_zero(self):
        assert format_time(-5) == "0:00"


class TestPlayPauseButtonSize:
    def test_button_has_fixed_width(self, panel):
        assert panel._play_btn.minimumWidth() == panel._play_btn.maximumWidth()

    def test_width_unchanged_across_play_pause_toggle(self, panel):
        widths = set()
        for paused in (False, True, False, True):
            panel._handle_pause(paused)
            widths.add(panel._play_btn.width())
        assert len(widths) == 1

    def test_fixed_width_fits_both_labels(self, panel):
        metrics = panel._play_btn.fontMetrics()
        needed = max(metrics.horizontalAdvance("Play"), metrics.horizontalAdvance("Pause"))
        assert panel._play_btn.width() >= needed


class TestSpeedSlider:
    def test_default_speed_is_1x(self, panel):
        assert SPEED_STEPS[DEFAULT_SPEED_INDEX] == 1.0
        assert panel._speed_slider.value() == DEFAULT_SPEED_INDEX
        assert panel._speed_label.text() == "1.0x"

    def test_slider_is_notched_over_discrete_steps(self, panel):
        assert panel._speed_slider.minimum() == 0
        assert panel._speed_slider.maximum() == len(SPEED_STEPS) - 1
        assert panel._speed_slider.tickInterval() == 1

    def test_moving_slider_updates_label(self, panel):
        panel._speed_slider.setValue(0)
        assert panel._speed_label.text() == f"{SPEED_STEPS[0]:g}x"

        panel._speed_slider.setValue(len(SPEED_STEPS) - 1)
        assert panel._speed_label.text() == f"{SPEED_STEPS[-1]:g}x"

    def test_moving_slider_without_a_player_does_not_raise(self, panel):
        assert panel._player is None
        panel._speed_slider.setValue(0)  # must not raise
