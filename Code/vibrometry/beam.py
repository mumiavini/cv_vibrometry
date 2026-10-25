"""
Analytical cantilever model and validation criterion
(TCC: "Modelagem e Simulação" and "Estratégia de Validação dos Resultados").

The ruler is modelled as a uniform rectangular Euler-Bernoulli beam clamped
at one end.  The natural frequency of bending mode i is (eq:fn_cantilever):

    f_n,i = (beta_i L)^2 / (2 pi L^2) * sqrt(E I / (rho A))

with I = b h^3 / 12 and A = b h.  The equivalent 1-DOF parameters at the
free tip are (eq:keq_meq):

    k_eq = 3 E I / L^3        m_eq = 0.2357 rho A L
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# characteristic roots (beta_i * L) of the clamped-free beam
BETA_L = (1.8751, 4.6941, 7.8548)

# reference material parameters (TCC tab:parametros_materiais)
MATERIALS: dict[str, dict[str, float]] = {
    "steel":         {"E": 193e9, "rho": 7850.0},   # stainless steel
    "polypropylene": {"E": 1.5e9, "rho": 900.0},
    "polystyrene":   {"E": 3.2e9, "rho": 1050.0},   # school ruler
    "aluminum_6351_t6": {"E": 69e9, "rho": 2710.0},  # bench test bar
}


@dataclass
class CantileverBeam:
    """Clamped-free beam with rectangular cross-section (SI units).

    Parameters
    ----------
    length : free (cantilevered) length L [m].
    width : cross-section width b [m].
    thickness : cross-section thickness h [m] (bending direction).
    E : Young's modulus [Pa].
    rho : density [kg/m^3].
    """

    length: float
    width: float
    thickness: float
    E: float
    rho: float

    @classmethod
    def from_material(cls, length: float, width: float, thickness: float,
                      material: str) -> "CantileverBeam":
        try:
            props = MATERIALS[material]
        except KeyError:
            raise ValueError(
                f"Unknown material '{material}'; options: {sorted(MATERIALS)}"
            ) from None
        return cls(length, width, thickness, props["E"], props["rho"])

    @property
    def area(self) -> float:
        """Cross-section area A = b h [m^2]."""
        return self.width * self.thickness

    @property
    def inertia(self) -> float:
        """Second moment of area I = b h^3 / 12 [m^4]."""
        return self.width * self.thickness ** 3 / 12.0

    def natural_frequency(self, mode: int = 1) -> float:
        """Natural frequency of bending mode ``mode`` [Hz] (eq:fn_cantilever)."""
        if not 1 <= mode <= len(BETA_L):
            raise ValueError(f"mode must be in 1..{len(BETA_L)}")
        beta_l = BETA_L[mode - 1]
        return (beta_l ** 2 / (2.0 * np.pi * self.length ** 2)) * np.sqrt(
            self.E * self.inertia / (self.rho * self.area)
        )

    @property
    def k_eq(self) -> float:
        """Equivalent tip stiffness k_eq = 3EI/L^3 [N/m] (eq:keq_meq)."""
        return 3.0 * self.E * self.inertia / self.length ** 3

    @property
    def m_eq(self) -> float:
        """Equivalent tip mass m_eq = 0.2357 rho A L [kg] (eq:keq_meq)."""
        return 0.2357 * self.rho * self.area * self.length

    def mass_loaded_frequency(self, added_mass: float) -> float:
        """First natural frequency with a point mass at the tip [Hz]
        (mass-loading effect, eq:mass_loading)."""
        return self.natural_frequency(1) * np.sqrt(
            self.m_eq / (self.m_eq + added_mass)
        )


@dataclass
class SpringSupportedBeam:
    """Clamped-free beam with a linear spring (and optional lumped mass) at
    the free end — the bench configuration of the TCC.

    Boundary conditions at x = L:  EI w'' = 0  and  EI w''' = (k - M w^2) w,
    with k the spring stiffness and M the lumped tip mass (e.g. the
    accelerometer).  Mode shapes are W = A(cos bx - cosh bx) + B(sin bx -
    sinh bx); the allowed b follow from the roots of the 2x2 determinant,
    found numerically.  For k = M = 0 this reduces to the plain cantilever
    (eq:fn_cantilever); for k -> inf, to the clamped-pinned beam.

    Parameters
    ----------
    beam : the underlying uniform cantilever.
    spring_k : tip spring stiffness k [N/m].
    tip_mass : lumped mass M at the free end [kg].
    """

    beam: CantileverBeam
    spring_k: float
    tip_mass: float = 0.0

    def _determinant(self, beta_l: float) -> float:
        b = self.beam
        beta = beta_l / b.length
        omega2 = beta ** 4 * b.E * b.inertia / (b.rho * b.area)
        k_e = self.spring_k - self.tip_mass * omega2
        c, s = np.cos(beta_l), np.sin(beta_l)
        ch, sh = np.cosh(beta_l), np.sinh(beta_l)
        w = np.array([c - ch, s - sh])
        w2 = beta ** 2 * np.array([-c - ch, -s - sh])
        w3 = beta ** 3 * np.array([s - sh, -c - ch])
        shear = b.E * b.inertia * w3 - k_e * w
        return float(w2[0] * shear[1] - w2[1] * shear[0])

    def _roots(self, n_modes: int) -> list[float]:
        grid = np.linspace(1e-3, 4.0 * n_modes + 4.0, 4000 * n_modes)
        vals = np.array([self._determinant(x) for x in grid])
        roots: list[float] = []
        for i in np.nonzero(vals[:-1] * vals[1:] < 0)[0]:
            lo, hi = grid[i], grid[i + 1]
            f_lo = vals[i]
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                f_mid = self._determinant(mid)
                if f_lo * f_mid <= 0:
                    hi = mid
                else:
                    lo, f_lo = mid, f_mid
            roots.append(0.5 * (lo + hi))
            if len(roots) == n_modes:
                break
        if len(roots) < n_modes:
            raise RuntimeError("could not bracket the requested modes")
        return roots

    def natural_frequency(self, mode: int = 1) -> float:
        """Natural frequency of bending mode ``mode`` [Hz]."""
        if mode < 1:
            raise ValueError("mode must be >= 1")
        b = self.beam
        beta_l = self._roots(mode)[mode - 1]
        return (beta_l ** 2 / (2.0 * np.pi * b.length ** 2)) * np.sqrt(
            b.E * b.inertia / (b.rho * b.area)
        )

    def mode_shape(self, x: np.ndarray, mode: int = 1) -> np.ndarray:
        """Mode shape at positions ``x`` [m] from the clamp, normalised to 1
        at the free end."""
        b = self.beam
        beta_l = self._roots(mode)[mode - 1]
        beta = beta_l / b.length
        c, s = np.cos(beta_l), np.sin(beta_l)
        ch, sh = np.cosh(beta_l), np.sinh(beta_l)
        # null vector of the W'' = 0 row
        coef_a, coef_b = -(-s - sh), (-c - ch)
        bx = beta * np.asarray(x, dtype=float)
        shape = (coef_a * (np.cos(bx) - np.cosh(bx))
                 + coef_b * (np.sin(bx) - np.sinh(bx)))
        tip = (coef_a * (c - ch) + coef_b * (s - sh))
        return shape / tip

    @property
    def k_eq(self) -> float:
        """Equivalent tip stiffness: beam + spring [N/m]."""
        return self.beam.k_eq + self.spring_k

    @property
    def m_eq(self) -> float:
        """Equivalent tip mass: beam (0.2357 rho A L) + lumped mass [kg]."""
        return self.beam.m_eq + self.tip_mass

    def one_dof_frequency(self) -> float:
        """Single-degree-of-freedom approximation sqrt(k_eq / m_eq) / 2 pi
        [Hz], for comparison with the exact result."""
        return float(np.sqrt(self.k_eq / self.m_eq) / (2.0 * np.pi))


@dataclass
class ValidationResult:
    f_measured: float    # optically identified frequency [Hz]
    f_analytical: float  # Euler-Bernoulli prediction [Hz]
    error_percent: float
    passed: bool         # eq:criterio_validacao, epsilon < tolerance


def validate_frequency(
    f_measured: float,
    f_analytical: float,
    tolerance_percent: float = 5.0,
) -> ValidationResult:
    """Phase-1 validation criterion (eq:criterio_validacao):

        epsilon = |f_opt - f_anal| / f_anal * 100% < tolerance
    """
    error = abs(f_measured - f_analytical) / f_analytical * 100.0
    return ValidationResult(
        f_measured=float(f_measured),
        f_analytical=float(f_analytical),
        error_percent=float(error),
        passed=bool(error < tolerance_percent),
    )
