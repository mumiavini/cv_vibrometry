"""
Module 3 — Gabor filter bank and phase extraction
(TCC: "Banco de filtros de Gabor e extração de fase").

A bank of N_theta x N_omega complex Gabor filters is convolved with the
image patches.  Each filter response C = A * exp(j*phi) provides a local
amplitude map A (texture strength in the filter band) and a local phase map
phi that encodes the sub-pixel position of the structure
(eq:gabor_kernel, eq:gabor_coef in the TCC).

For a translation delta along the filter direction u = (cos(theta), sin(theta)),
the local phase changes by  d_phi ≈ -omega0 * (delta . u)
(eq:fase_deslocamento), so the displacement projection is recovered as
(delta . u) = -d_phi / omega0 without any explicit pattern search.

The displacement vector (dx, dy) is reconstructed from the projections of
all filters in the bank through an amplitude-weighted least-squares fit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


def gabor_kernel(
    wavelength: float,
    theta: float,
    sigma: float | None = None,
    n_sigma: float = 3.0,
) -> np.ndarray:
    """Complex 2-D Gabor kernel (eq:gabor_kernel).

        G(x, y) = exp(-(x'^2 + y'^2) / (2 sigma^2)) * exp(j omega0 x')

    with (x', y') the coordinates rotated by ``theta`` and
    omega0 = 2*pi / wavelength [rad/pixel].  The kernel mean is removed so
    that uniform (texture-less) regions produce zero response.

    Parameters
    ----------
    wavelength : spatial wavelength lambda of the carrier [pixels].
    theta : filter orientation [rad]; the carrier oscillates along x'.
    sigma : Gaussian envelope width [pixels]; defaults to 0.56 * wavelength
        (approximately one octave of spatial bandwidth).
    """
    omega0 = 2.0 * np.pi / wavelength
    if sigma is None:
        sigma = 0.56 * wavelength

    half = int(np.ceil(n_sigma * sigma))
    y, x = np.mgrid[-half: half + 1, -half: half + 1].astype(np.float64)
    x_r = x * np.cos(theta) + y * np.sin(theta)
    y_r = -x * np.sin(theta) + y * np.cos(theta)

    envelope = np.exp(-(x_r ** 2 + y_r ** 2) / (2.0 * sigma ** 2))
    kernel = envelope * np.exp(1j * omega0 * x_r)
    kernel -= kernel.mean()          # remove DC sensitivity
    kernel /= np.abs(kernel).sum()   # normalise gain
    return kernel


@dataclass
class GaborFilter:
    theta: float        # orientation [rad]
    omega0: float       # central spatial frequency [rad/pixel]
    kernel: np.ndarray  # complex kernel


@dataclass
class GaborBank:
    """Bank of N_theta x N_omega complex Gabor filters.

    Default: 4 orientations (0, 45, 90, 135 deg) x 2 wavelengths (8, 16 px),
    suitable for high-contrast markers a few pixels to a few tens of pixels
    in size.
    """

    wavelengths: tuple[float, ...] = (8.0, 16.0)
    orientations: tuple[float, ...] = (0.0, np.pi / 4, np.pi / 2, 3 * np.pi / 4)
    sigma_factor: float = 0.56
    filters: list[GaborFilter] = field(init=False)

    def __post_init__(self) -> None:
        self.filters = [
            GaborFilter(
                theta=theta,
                omega0=2.0 * np.pi / lam,
                kernel=gabor_kernel(lam, theta, sigma=self.sigma_factor * lam),
            )
            for lam in self.wavelengths
            for theta in self.orientations
        ]

    @property
    def pad(self) -> int:
        """Half-size of the largest kernel: margin needed around a patch so
        that its interior is free of convolution edge effects."""
        return max(f.kernel.shape[0] // 2 for f in self.filters)

    def responses(self, patch: np.ndarray) -> list[np.ndarray]:
        """Convolve the patch with every filter (eq:conv_gabor).

        Returns one complex response map C = A exp(j phi) per filter.
        """
        patch = patch.astype(np.float32)
        patch = patch - patch.mean()
        out = []
        for f in self.filters:
            real = cv2.filter2D(patch, cv2.CV_32F, f.kernel.real,
                                borderType=cv2.BORDER_REPLICATE)
            imag = cv2.filter2D(patch, cv2.CV_32F, f.kernel.imag,
                                borderType=cv2.BORDER_REPLICATE)
            out.append(real + 1j * imag)
        return out

    def phase_displacement(
        self,
        ref_responses: list[np.ndarray],
        cur_responses: list[np.ndarray],
        margin: int | None = None,
    ) -> tuple[np.ndarray, float]:
        """Sub-pixel displacement between two patches from their phase maps.

        For each filter the wrapped phase difference is aggregated over the
        patch through the amplitude-weighted complex sum
        S = sum( C_cur * conj(C_ref) ), whose angle is the
        amplitude-weighted mean of d_phi (pixels with low amplitude A carry
        unreliable phase and contribute little — TCC eq:fase_deslocamento
        discussion).  The projections  (delta . u_k) = +angle(S_k)/omega0_k
        are then combined in a weighted least-squares fit for (dx, dy).

        Sign note: cv2.filter2D computes *correlation* (kernel not flipped),
        so the local response phase decreases along the filter direction,
        phi(x) ≈ phi0 - omega0 (x . u), and a translation t produces
        d_phi = +omega0 (t . u) — opposite to the convolution convention of
        eq:fase_deslocamento.

        Valid for |delta . u| < wavelength/2 along each direction, i.e. this
        measures the *sub-pixel residual* after coarse alignment.

        Returns
        -------
        (dx, dy) : displacement of the current patch w.r.t. the reference
            [pixels, image coordinates: +x right, +y down].
        weight : total amplitude weight (confidence of the estimate).
        """
        if margin is None:
            margin = self.pad
        interior = (slice(margin, -margin or None), slice(margin, -margin or None))

        directions = []
        projections = []
        weights = []
        for f, c_ref, c_cur in zip(self.filters, ref_responses, cur_responses):
            s = (c_cur[interior] * np.conj(c_ref[interior])).sum()
            w = np.abs(s)
            if w <= 0.0:
                continue
            d_phi = np.angle(s)
            directions.append((np.cos(f.theta), np.sin(f.theta)))
            projections.append(d_phi / f.omega0)
            weights.append(w)

        if len(weights) < 2:
            return np.zeros(2), 0.0

        a = np.asarray(directions)            # (k, 2)
        b = np.asarray(projections)           # (k,)
        w = np.asarray(weights)
        aw = a * w[:, None]
        try:
            delta = np.linalg.solve(a.T @ aw, aw.T @ b)
        except np.linalg.LinAlgError:
            return np.zeros(2), 0.0
        return delta, float(w.sum())
