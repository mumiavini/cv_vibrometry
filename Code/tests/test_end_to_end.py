"""End-to-end verification on synthetic video + accelerometer with known
ground truth: the whole chain the desktop app uses (``process_session``)."""

import pytest

from vibrometry.session import Session
from vibrometry.synthetic import generate_validation_dataset
from vibrometry.workflow import process_session


@pytest.mark.parametrize("kind", ["forced", "free"])
def test_synthetic_session(tmp_path, kind):
    ds = generate_validation_dataset(tmp_path, kind=kind, f=6.0, amplitude_mm=1.5,
                                     duration=5.0, size=(480, 270), acc_offset_s=0.4321)
    res = process_session(Session.load(ds["session"]), use_cache=False)
    assert res.error is None, res.error
    m = res.comparison.metrics
    assert res.comparison.offset_s == pytest.approx(0.4321, abs=0.5e-3)
    assert abs(m.freq_error_percent) < 0.1
    assert abs(m.amp_error_percent) < 3.0
    assert abs(m.phase_diff_deg) < 2.0
    if kind == "free":
        modal = res.analysis.modal["ponta"]
        assert modal.zeta_log_decrement == pytest.approx(0.01, rel=0.1)
        assert abs(modal.error_predicted_percent) < 1.0
