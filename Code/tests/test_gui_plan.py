"""Smoke test of the planning page and the ROI position control (offscreen Qt)."""

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from vibrometry.session import Session  # noqa: E402

SESSION = Path(__file__).resolve().parents[1] / "sessions" / "k1_cm_acc.vibro.json"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _page(app):
    """Plan page on the repository session with a fixed bench specimen (the
    session file itself may be edited by the user)."""
    from vibroapp.page_plan import PlanPage
    from vibroapp.state import AppState
    state = AppState()
    state.session = Session.load(SESSION)
    sp = state.session.specimen
    sp.support = "pinned"
    sp.tip_mass_g = 0.0
    sp.springs = [{"name": "mola k1", "x_mm": 632.0, "k_n_m": 1500.0,
                   "mass_g": 0.0, "hardware_g": 0.0}]
    sp.masses = [{"name": "acelerometro", "x_mm": 300.0, "mass_g": 5.0}]
    return state, PlanPage(state)


def test_plan_page_shows_the_fe_prediction_for_the_bench(app):
    state, page = _page(app)
    assert "elementos finitos" in page.cards_title.text()
    assert page.support.currentData() == "pinned"
    assert page.springs.rowCount() == 1 and page.masses.rowCount() == 1
    assert page.m_f1.value.text().startswith("11.7") or page.m_f1.value.text().startswith("11,7")
    assert "Massa não informada" in page.verdict.text()      # spring mass still missing


def test_editing_the_spring_mass_updates_the_prediction_and_the_session(app):
    state, page = _page(app)
    page.springs.item(0, 4).setText("383")       # hardware / effective mass [g]
    assert state.session.specimen.springs[0]["hardware_g"] == 383.0
    assert state.dirty
    text = page.m_f1.value.text().replace(",", ".")
    assert abs(float(text.split()[0]) - 7.6) < 0.05
    assert "Massa não informada" not in page.verdict.text()


def test_adding_and_removing_a_mass_row(app):
    state, page = _page(app)
    page.add_mass.click()
    assert len(state.session.specimen.masses) == 2
    page.masses.selectRow(1)
    page.del_mass.click()
    assert len(state.session.specimen.masses) == 1


def test_switching_to_clamped_without_attachments_uses_the_closed_form(app):
    state, page = _page(app)
    page.springs.removeRow(0)
    page.masses.removeRow(0)
    page.springs.edited.emit()
    page.support.setCurrentIndex(page.support.findData("clamped"))
    assert not state.session.specimen.uses_fe
    assert "engastada" in page.cards_title.text()
