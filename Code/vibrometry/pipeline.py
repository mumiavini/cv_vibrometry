"""
End-to-end orchestration of the optical vibrometry pipeline
(TCC: "Arquitetura do Software e Pipeline de Processamento").

Steps:
  1. frame import                       (video_io)
  2. ROI definition                     (roi)
  3. Gabor phase displacement tracking  (gabor + tracking)
  4. reference-ROI compensation, spatial calibration, spectral analysis
     and modal parameter extraction     (calibration + spectral)
  5. optional comparison with the Euler-Bernoulli cantilever model (beam)
  6. export of figures, time series (CSV) and modal results (JSON)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import polars as pl

from . import plotting
from .beam import CantileverBeam, ValidationResult, validate_frequency
from .gabor import GaborBank
from .roi import ROI
from .spectral import (
    LogDecrementResult,
    SpectralPeak,
    amplitude_spectrum,
    find_spectral_peaks,
    half_power_damping,
    log_decrement_damping,
    stft_spectrogram,
)
from .tracking import TrackResult, track_roi
from .video_io import VideoData


@dataclass
class PipelineConfig:
    """Analysis parameters.

    Parameters
    ----------
    scale_mm_per_px : spatial calibration factor s [mm/pixel]
        (eq:escala); if None, results are reported in pixels.
    beam : analytical cantilever model for Phase-1 validation; optional.
    axis : displacement component to analyse: "x", "y" or "auto"
        (auto picks, per ROI, the component with the largest variance).
    gabor_wavelengths : carrier wavelengths of the filter bank [px].
    gabor_orientations : filter orientations [rad].
    search_margin : half-size of the coarse-tracking search window [px].
    tolerance_percent : validation threshold (eq:criterio_validacao).
    """

    scale_mm_per_px: float | None = None
    beam: CantileverBeam | None = None
    axis: str = "auto"
    gabor_wavelengths: tuple[float, ...] = (8.0, 16.0)
    gabor_orientations: tuple[float, ...] = (
        0.0, np.pi / 4, np.pi / 2, 3 * np.pi / 4
    )
    search_margin: int = 60
    tolerance_percent: float = 5.0

    @property
    def unit(self) -> str:
        return "mm" if self.scale_mm_per_px is not None else "px"


@dataclass
class ROIModalResult:
    """Modal parameters identified for one measurement ROI."""

    name: str
    axis: str                                   # analysed component
    f_n: float | None                           # dominant frequency [Hz]
    zeta_half_power: float | None
    zeta_log_decrement: float | None
    peaks: list[SpectralPeak] = field(default_factory=list)
    validation: ValidationResult | None = None

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "axis": self.axis,
            "f_n_hz": self.f_n,
            "zeta_half_power": self.zeta_half_power,
            "zeta_log_decrement": self.zeta_log_decrement,
            "spectral_peaks": [asdict(p) for p in self.peaks],
        }
        if self.validation is not None:
            d["validation"] = asdict(self.validation)
        return d


class VibrometryPipeline:
    def __init__(
        self,
        video: VideoData,
        rois: list[ROI],
        config: PipelineConfig | None = None,
    ) -> None:
        if not rois:
            raise ValueError("At least one measurement ROI is required.")
        self.video = video
        self.config = config or PipelineConfig()
        self.measurement_rois = [r for r in rois if not r.is_reference]
        refs = [r for r in rois if r.is_reference]
        self.reference_roi = refs[0] if refs else None
        if not self.measurement_rois:
            raise ValueError("All supplied ROIs are reference ROIs.")

        self.bank = GaborBank(
            wavelengths=self.config.gabor_wavelengths,
            orientations=self.config.gabor_orientations,
        )

        # populated by run()
        self.tracks: dict[str, TrackResult] = {}
        self.signals: dict[str, np.ndarray] = {}      # compensated, calibrated
        self.spectra: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self.decays: dict[str, LogDecrementResult | None] = {}
        self.modal_results: list[ROIModalResult] = []

    # ------------------------------------------------------------------ #
    def run(self) -> list[ROIModalResult]:
        cfg = self.config
        video = self.video

        # --- stage 3: displacement tracking ---------------------------- #
        all_rois = list(self.measurement_rois)
        if self.reference_roi is not None:
            all_rois.append(self.reference_roi)
        for r in all_rois:
            self.tracks[r.name] = track_roi(
                video.frames, r, bank=self.bank,
                search_margin=cfg.search_margin,
            )

        # --- stage 4a: rigid-body compensation (eq:compensacao) -------- #
        ref_disp = (
            self.tracks[self.reference_roi.name].displacement
            if self.reference_roi is not None
            else np.zeros((video.n_frames, 2))
        )

        self.modal_results = []
        for r in self.measurement_rois:
            disp = self.tracks[r.name].displacement - ref_disp

            # component selection
            axis = cfg.axis
            if axis == "auto":
                axis = "x" if disp[:, 0].std() >= disp[:, 1].std() else "y"
            sig = disp[:, 0] if axis == "x" else disp[:, 1]

            # DC removal and spatial calibration (eq:deslocamento_fisico)
            sig = sig - sig.mean()
            if cfg.scale_mm_per_px is not None:
                sig = sig * cfg.scale_mm_per_px
            self.signals[r.name] = sig

            # --- stage 4b: spectral analysis (eq:fft) ------------------ #
            freqs, amp = amplitude_spectrum(sig, video.fps)
            self.spectra[r.name] = (freqs, amp)
            peaks = find_spectral_peaks(freqs, amp)

            f_n = peaks[0].frequency if peaks else None
            zeta_hp = (
                half_power_damping(freqs, amp, f_n) if f_n is not None else None
            )
            decay = (
                log_decrement_damping(sig, video.fps, f_n)
                if f_n is not None else None
            )
            self.decays[r.name] = decay

            validation = None
            if cfg.beam is not None and f_n is not None:
                validation = validate_frequency(
                    f_n,
                    cfg.beam.natural_frequency(1),
                    tolerance_percent=cfg.tolerance_percent,
                )

            self.modal_results.append(ROIModalResult(
                name=r.name,
                axis=axis,
                f_n=f_n,
                zeta_half_power=zeta_hp,
                zeta_log_decrement=decay.zeta if decay else None,
                peaks=peaks,
                validation=validation,
            ))

        return self.modal_results

    # ------------------------------------------------------------------ #
    def export(self, output_dir: str | Path) -> Path:
        """Save figures, time series (CSV) and modal results (JSON)."""
        if not self.modal_results:
            raise RuntimeError("Call run() before export().")
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        cfg = self.config
        unit = cfg.unit
        times = self.video.times

        # ---- CSV: displacement signals -------------------------------- #
        df = pl.DataFrame({"time_s": times, **{
            f"{name}_{unit}": sig for name, sig in self.signals.items()
        }})
        df.write_csv(out / "displacement_signals.csv")

        # ---- JSON: modal results --------------------------------------- #
        summary = {
            "video": self.video.path,
            "fps": self.video.fps,
            "n_frames": self.video.n_frames,
            "duration_s": self.video.duration,
            "nyquist_hz": self.video.nyquist,
            "unit": unit,
            "scale_mm_per_px": cfg.scale_mm_per_px,
            "rois": [m.to_dict() for m in self.modal_results],
        }
        if cfg.beam is not None:
            summary["analytical_model"] = {
                "f_n1_hz": cfg.beam.natural_frequency(1),
                "k_eq_n_per_m": cfg.beam.k_eq,
                "m_eq_kg": cfg.beam.m_eq,
            }
        (out / "modal_results.json").write_text(json.dumps(summary, indent=2))

        # ---- figures ---------------------------------------------------- #
        f_anal = cfg.beam.natural_frequency(1) if cfg.beam is not None else None

        fig = plotting.plot_tracking_overview(
            self.video.reference_frame, self.tracks)
        fig.savefig(out / "tracking_overview.png", dpi=150)

        fig = plotting.plot_time_series(times, self.signals, unit=unit)
        fig.savefig(out / "displacement_time_series.png", dpi=150)

        for name in self.signals:
            freqs, amp = self.spectra[name]
            modal = next(m for m in self.modal_results if m.name == name)
            fig = plotting.plot_spectrum(
                freqs, amp, modal.peaks, f_analytical=f_anal, unit=unit,
                title=f"Amplitude spectrum — {name}",
            )
            fig.savefig(out / f"spectrum_{name}.png", dpi=150)

            decay = self.decays.get(name)
            if decay is not None:
                fig = plotting.plot_decay_fit(
                    times, self.signals[name], decay, unit=unit)
                fig.savefig(out / f"decay_fit_{name}.png", dpi=150)

            st, sf, sm = stft_spectrogram(self.signals[name], self.video.fps)
            fig = plotting.plot_spectrogram(st, sf, sm, unit=unit)
            fig.savefig(out / f"spectrogram_{name}.png", dpi=150)

        import matplotlib.pyplot as plt
        plt.close("all")
        return out

    # ------------------------------------------------------------------ #
    def report(self) -> str:
        """Plain-text summary of the identified modal parameters."""
        lines = [
            f"Video: {self.video.path}",
            f"  {self.video.n_frames} frames @ {self.video.fps:.2f} fps "
            f"({self.video.duration:.2f} s, Nyquist {self.video.nyquist:.2f} Hz)",
        ]
        cfg = self.config
        if cfg.beam is not None:
            lines.append(
                f"Analytical model: f_n1 = {cfg.beam.natural_frequency(1):.3f} Hz, "
                f"k_eq = {cfg.beam.k_eq:.2f} N/m, m_eq = {cfg.beam.m_eq * 1e3:.2f} g"
            )
        for m in self.modal_results:
            lines.append(f"ROI '{m.name}' (axis {m.axis}):")
            if m.f_n is None:
                lines.append("  no spectral peak identified")
                continue
            lines.append(f"  f_n = {m.f_n:.3f} Hz")
            if m.zeta_half_power is not None:
                lines.append(f"  zeta (half-power)    = {m.zeta_half_power:.4f}")
            if m.zeta_log_decrement is not None:
                lines.append(f"  zeta (log decrement) = {m.zeta_log_decrement:.4f}")
            if m.validation is not None:
                v = m.validation
                status = "PASSED" if v.passed else "FAILED"
                lines.append(
                    f"  validation vs analytical {v.f_analytical:.3f} Hz: "
                    f"error = {v.error_percent:.2f}% -> {status} "
                    f"(criterion < {cfg.tolerance_percent:.0f}%)"
                )
        return "\n".join(lines)
