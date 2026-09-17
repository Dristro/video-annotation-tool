from PySide6.QtCore import QCoreApplication
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from vat.models.cut import Cut  # noqa: E402
from vat.ui.continuation_link_dialog import ContinuationLinkDialog, resolve_link  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication | QCoreApplication:
    return QApplication.instance() or QApplication([])


class TestResolveLink:
    def test_completing_a_candidate_takes_its_id(self) -> None:
        cut = Cut(start=0.0, end=5.0)
        front = Cut(start=50.0, end=60.0, continuation_id="chain", continues_forward=True)
        assert resolve_link(cut, front, False) == ("chain", False)

    def test_completing_and_continuing_propagates_the_same_id(self) -> None:
        # A middle segment of a 3+-video chain: one id straight through.
        cut = Cut(start=0.0, end=5.0)
        front = Cut(start=50.0, end=60.0, continuation_id="chain", continues_forward=True)
        assert resolve_link(cut, front, True) == ("chain", True)

    def test_continuing_only_keeps_an_existing_forward_id(self) -> None:
        cut = Cut(start=0.0, end=5.0, continuation_id="mine", continues_forward=True)
        assert resolve_link(cut, None, True) == ("mine", True)

    def test_continuing_only_mints_a_fresh_id_when_there_was_none(self) -> None:
        cut = Cut(start=0.0, end=5.0)
        cid, forward = resolve_link(cut, None, True)
        assert forward is True and cid and cid != "mine"

    def test_a_back_half_id_is_not_reused_as_a_forward_id(self) -> None:
        # Unchecking "completes" while checking "continues" must not keep
        # the old back-half id: that would falsely link to the previous
        # video's cut again.
        cut = Cut(start=0.0, end=5.0, continuation_id="prev", continues_forward=False)
        cid, forward = resolve_link(cut, None, True)
        assert forward is True and cid != "prev"

    def test_neither_means_unlinked(self) -> None:
        cut = Cut(start=0.0, end=5.0, continuation_id="prev", continues_forward=True)
        assert resolve_link(cut, None, False) == (None, False)


class TestDialog:
    def test_preselects_current_back_half_and_forward_state(self, qapp) -> None:
        front = Cut(start=50.0, end=60.0, label="goal", continuation_id="chain", continues_forward=True)
        other = Cut(start=10.0, end=20.0, label="foul", continuation_id="x", continues_forward=True)
        cut = Cut(start=0.0, end=5.0, continuation_id="chain", continues_forward=True)

        dialog = ContinuationLinkDialog(cut, [other, front], next_video_available=True, previous_video_name="a.mp4")

        assert dialog._forward_checkbox.isChecked() is True
        assert dialog._candidate_radios[1].isChecked() is True
        assert dialog.completes() is front
        assert dialog.resolve() == ("chain", True)

    def test_none_selected_when_cut_is_unlinked(self, qapp) -> None:
        front = Cut(start=50.0, end=60.0, continuation_id="chain", continues_forward=True)
        dialog = ContinuationLinkDialog(Cut(start=0.0, end=5.0), [front], True, "a.mp4")
        assert dialog._none_radio.isChecked() is True
        assert dialog.completes() is None

    def test_forward_checkbox_disabled_without_a_next_video(self, qapp) -> None:
        dialog = ContinuationLinkDialog(Cut(start=0.0, end=5.0), [], next_video_available=False, previous_video_name=None)
        assert dialog._forward_checkbox.isEnabled() is False
        assert dialog._candidate_radios == []

    def test_choices_drive_resolve(self, qapp) -> None:
        front = Cut(start=50.0, end=60.0, continuation_id="chain", continues_forward=True)
        dialog = ContinuationLinkDialog(Cut(start=0.0, end=5.0), [front], True, "a.mp4")
        dialog._candidate_radios[0].setChecked(True)
        dialog._forward_checkbox.setChecked(True)
        assert dialog.resolve() == ("chain", True)
