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
