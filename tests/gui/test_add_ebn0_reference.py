"""The form of Add Eb/N0 entry asks, optionally, for the error rate the entry's Eb/N0 refers to
(2.1.0)."""

from __future__ import annotations

import pytest

from budget_gui.add_ebn0_dialog import AddEbn0Dialog

pytestmark = pytest.mark.gui


def test_the_form_has_optional_ber_and_fer_fields(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddEbn0Dialog([])
    qtbot.addWidget(dialog)
    dialog.modulation_edit.setText("QPSK")
    dialog.coding_edit.setText("rate 1/2")
    assert dialog.add_button.isEnabled()  # both are optional
    answers = dialog.answers()
    assert answers.target_ber == "" and answers.target_fer == ""

    dialog.ber_edit.setText("1e-5")
    dialog.fer_edit.setText("1e-7")
    assert dialog.add_button.isEnabled()
    answers = dialog.answers()
    assert (answers.target_ber, answers.target_fer) == ("1e-5", "1e-7")


def test_a_bad_rate_is_said_and_blocks_the_entry(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddEbn0Dialog([])
    qtbot.addWidget(dialog)
    dialog.modulation_edit.setText("QPSK")
    dialog.coding_edit.setText("none")
    dialog.ber_edit.setText("two")
    assert not dialog.add_button.isEnabled()
    assert "bit error rate" in dialog.error_label.text().lower()


def test_the_form_says_the_rate_is_a_reference_the_user_supplies(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddEbn0Dialog([])
    qtbot.addWidget(dialog)
    assert (
        "supply" in dialog.ber_edit.toolTip().lower() or "from" in dialog.ber_edit.toolTip().lower()
    )
    assert dialog.ber_edit.placeholderText() and dialog.fer_edit.placeholderText()
