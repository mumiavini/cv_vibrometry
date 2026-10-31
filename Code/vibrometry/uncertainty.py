"""
Uncertainty and repeatability (TODO B2 / E2), following the GUM approach:

* frequency of one record — Type A from segments of the record (spread of
  the sine-fit frequency of K consecutive segments) and the spectral
  resolution 1/T of the whole record, reported side by side;
* repeatability over N takes — mean, standard deviation, coefficient of
  variation and Student-t confidence interval;
* model prediction — propagation of the input uncertainties (stiffness,
  masses, lengths, positions, E, rho, section) through the finite-element
  model, by linear sensitivity coefficients (u_f^2 = sum (df/dp_i u_i)^2) and,
  optionally, by Monte Carlo;
* spatial scale and relative errors between two uncertain quantities.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from .analysis import dominant_frequency, fit_sine


# --------------------------------------------------------------------------- #
# frequency of one record
# --------------------------------------------------------------------------- #
@dataclass
class FrequencyUncertainty:
    f: float                    # sine-fit frequency of the whole record [Hz]
    resolution: float           # 1 / T [Hz]
    segments: list[float]       # sine-fit frequency of each segment [Hz]
    u_type_a: float             # std(segments) / sqrt(K) [Hz]

    @property
    def u(self) -> float:
        """Standard uncertainty adopted: the Type A value (the sine fit
        resolves well below 1/T; the resolution is reported for reference)."""
        return self.u_type_a

    def to_dict(self) -> dict:
        return {"f_hz": self.f, "u_hz": self.u, "u_rel_pct": 100 * self.u / self.f,
                "resolucao_hz": self.resolution, "segmentos_hz": self.segments}


def frequency_uncertainty(t: np.ndarray, x: np.ndarray, fs: float,
                          n_segments: int = 4,
                          f0: float | None = None) -> FrequencyUncertainty | None:
    t = np.asarray(t, float)
    x = np.asarray(x, float) - np.mean(x)
    f0 = f0 or dominant_frequency(x, fs)
    if not f0:
        return None
    f_all = fit_sine(t, x, f0).frequency
    n = t.size // n_segments
    seg = []
    for k in range(n_segments):
        s = slice(k * n, (k + 1) * n)
        if t[s].size < 8 or (t[s][-1] - t[s][0]) * f_all < 2.0:
            continue
        xs = x[s] - x[s].mean()
        seg.append(float(fit_sine(t[s], xs, f_all, rel_span=0.05).frequency))
    u_a = float(np.std(seg, ddof=1) / np.sqrt(len(seg))) if len(seg) >= 2 else float("nan")
    return FrequencyUncertainty(float(f_all), float(1.0 / (t[-1] - t[0])), seg, u_a)


# --------------------------------------------------------------------------- #
# repeatability
# --------------------------------------------------------------------------- #
@dataclass
class Repeatability:
    n: int
    mean: float
    std: float
    cv_percent: float
    ci95: tuple[float, float]   # Student-t, two-sided

    def to_dict(self) -> dict:
        return {"n": self.n, "media": self.mean, "desvio": self.std,
                "cv_pct": self.cv_percent, "ic95": list(self.ci95)}


def repeatability(values) -> Repeatability:
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], float)
    if v.size < 2:
        raise ValueError("at least two values are needed")
    m, s = float(v.mean()), float(v.std(ddof=1))
    h = float(stats.t.ppf(0.975, v.size - 1) * s / np.sqrt(v.size))
    return Repeatability(int(v.size), m, s, 100.0 * s / abs(m), (m - h, m + h))


# --------------------------------------------------------------------------- #
# model prediction
# --------------------------------------------------------------------------- #
_PATH = re.compile(r"^(\w+)(?:\[(\d+)\]\.(\w+))?$")


def _get(spec, path: str) -> float:
    m = _PATH.match(path)
    if not m:
        raise KeyError(path)
    attr, idx, key = m.groups()
    obj = getattr(spec, attr)
    return float(obj[int(idx)][key]) if idx is not None else float(obj)


def _set(spec, path: str, value: float) -> None:
    attr, idx, key = _PATH.match(path).groups()
    if idx is None:
        setattr(spec, attr, float(value))
    else:
        getattr(spec, attr)[int(idx)][key] = float(value)


@dataclass
class ModelUncertainty:
    f: float                                   # nominal prediction [Hz]
    u: float                                   # combined standard uncertainty [Hz]
    contributions: dict[str, dict] = field(default_factory=dict)
    mc_mean: float | None = None
    mc_std: float | None = None

    def to_dict(self) -> dict:
        return {"f_hz": self.f, "u_hz": self.u, "u_rel_pct": 100 * self.u / self.f,
                "contribuicoes": self.contributions,
                "monte_carlo": None if self.mc_std is None else
                {"media_hz": self.mc_mean, "desvio_hz": self.mc_std}}


def model_uncertainty(specimen, uncertainties: dict[str, float],
                      mode: int = 1, n_mc: int = 0, seed: int = 0,
                      n_elements: int = 100) -> ModelUncertainty:
    """Propagate standard uncertainties of the specimen parameters to the
    predicted frequency of elastic mode ``mode``.

    ``uncertainties`` maps parameter paths to standard uncertainties in the
    parameter's own unit, e.g. ``{"springs[0].k_n_m": 30, "springs[0].mass_g":
    1, "masses[0].x_mm": 2, "L_mm": 1, "E_gpa": 2}``. Paths are attributes of
    ``SpecimenCfg`` or ``list[index].key`` for springs and masses.
    """
    def f_of(spec) -> float:
        if spec.uses_fe:
            return float(spec.fe_model(n_elements=n_elements).elastic_frequency(mode))
        return float(spec.predicted_frequencies(mode)[mode - 1])

    f0 = f_of(specimen)
    contrib: dict[str, dict] = {}
    total = 0.0
    for path, u in uncertainties.items():
        if not u:
            continue
        p0 = _get(specimen, path)
        h = 0.5 * u
        sp, sm = copy.deepcopy(specimen), copy.deepcopy(specimen)
        _set(sp, path, p0 + h)
        _set(sm, path, p0 - h)
        c = (f_of(sp) - f_of(sm)) / (2.0 * h)            # sensitivity df/dp
        contrib[path] = {"valor": p0, "u": u, "sensibilidade_hz_por_unidade": c,
                         "u_f_hz": abs(c) * u}
        total += (c * u) ** 2
    u_f = float(np.sqrt(total))
    for d in contrib.values():
        d["parcela_pct"] = 100.0 * d["u_f_hz"] ** 2 / total if total > 0 else 0.0
    res = ModelUncertainty(f0, u_f, contrib)
    if n_mc:
        rng = np.random.default_rng(seed)
        fs = []
        for _ in range(n_mc):
            s = copy.deepcopy(specimen)
            for path, u in uncertainties.items():
                if u:
                    _set(s, path, _get(specimen, path) + rng.normal(0.0, u))
            fs.append(f_of(s))
        res.mc_mean, res.mc_std = float(np.mean(fs)), float(np.std(fs, ddof=1))
    return res


# --------------------------------------------------------------------------- #
# scale and relative errors
# --------------------------------------------------------------------------- #
def scale_uncertainty(d_ref_mm: float, u_d_ref_mm: float,
                      d_px: float, u_d_px: float) -> tuple[float, float]:
    """s = d_ref / d_px and its standard uncertainty (eq:escala)."""
    s = d_ref_mm / d_px
    u = s * np.hypot(u_d_ref_mm / d_ref_mm, u_d_px / d_px)
    return float(s), float(u)


def relative_error(q: float, u_q: float, q_ref: float, u_ref: float) -> tuple[float, float]:
    """eps = (q - q_ref) / q_ref * 100 [%] and its standard uncertainty,
    for uncorrelated q and q_ref."""
    eps = 100.0 * (q - q_ref) / q_ref
    u = 100.0 * np.hypot(u_q / q_ref, q * u_ref / q_ref ** 2)
    return float(eps), float(u)
