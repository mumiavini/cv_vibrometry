"""
Static stiffness test of the bench springs (roteiro de laboratório, 1.2).

The spring hangs from the support where it works and known forces are applied
at its lower end; the length is read at each load. The stiffness is the slope
of F × extension, fitted by least squares with a free intercept (so a small
seating of the hook/thread at the first load shifts the line instead of
biasing the slope), with its standard error from the residuals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass
class StiffnessFit:
    k: float                    # slope dF/dx [N/m]
    u_k: float                  # standard error of the slope [N/m]
    intercept_n: float          # F at zero extension [N]
    r2: float
    secant: float               # F_max / x(F_max) from the first reading [N/m]
    incremental: list[float]    # dF/dx between consecutive readings [N/m]
    n: int

    @property
    def rel_u(self) -> float:
        return self.u_k / self.k if self.k else float("nan")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rel_u"] = self.rel_u
        return d


def fit_spring_stiffness(force_n, length_m) -> StiffnessFit:
    """Least-squares stiffness F = k (L - L0) + c from paired readings of
    force [N] and spring length (or any position of the loaded end) [m].
    Needs at least three readings; they need not be sorted."""
    f = np.asarray(force_n, dtype=float)
    x = np.asarray(length_m, dtype=float)
    if f.shape != x.shape or f.size < 3:
        raise ValueError("need at least three (force, length) pairs of equal size")
    order = np.argsort(f)
    f, x = f[order], x[order]
    ext = x - x[0]
    if np.ptp(ext) <= 0:
        raise ValueError("the length does not change with the load")
    A = np.vstack([ext, np.ones_like(ext)]).T
    (k, c), *_ = np.linalg.lstsq(A, f, rcond=None)
    res = f - A @ np.array([k, c])
    dof = f.size - 2
    s2 = float(res @ res) / dof if dof > 0 else 0.0
    u_k = float(np.sqrt(s2 / np.sum((ext - ext.mean()) ** 2)))
    ss_tot = float(np.sum((f - f.mean()) ** 2))
    r2 = 1.0 - float(res @ res) / ss_tot if ss_tot > 0 else 1.0
    with np.errstate(divide="ignore", invalid="ignore"):
        incr = np.diff(f) / np.diff(ext)
    secant = float((f[-1] - f[0]) / ext[-1]) if ext[-1] else float("nan")
    return StiffnessFit(float(k), u_k, float(c), r2, secant,
                        [float(v) for v in incr], int(f.size))
