"""
vibrometry — Optical vibrometry pipeline (phase-based motion estimation).

Implements the processing pipeline described in the TCC
"Vibrometria óptica aplicada para medição de vibrações em testes
dinâmicos de bancada" (Trento, PUCPR):

    1. video_io      — frame import (grayscale, reference frame)
    2. roi           — measurement / reference ROI definition
    3. gabor         — Gabor filter bank and phase extraction
       tracking      — coarse template tracking + phase-based sub-pixel refinement
    4. spectral      — FFT (Hann), peak picking, half-power and log-decrement damping
    calibration      — mm/pixel spatial scale factor
    beam             — Euler-Bernoulli cantilever analytical model and validation
    pipeline         — end-to-end orchestration and result export
    synthetic        — synthetic cantilever video generator (ground-truth checks)
"""

from .video_io import VideoData, load_video
from .roi import ROI, save_rois, load_rois, select_rois_interactive
from .gabor import GaborBank
from .tracking import track_roi, TrackResult
from .spectral import (
    amplitude_spectrum,
    find_spectral_peaks,
    half_power_damping,
    log_decrement_damping,
    stft_spectrogram,
)
from .calibration import scale_from_pixels, scale_from_points
from .beam import CantileverBeam, MATERIALS, validate_frequency
from .pipeline import VibrometryPipeline, PipelineConfig

__all__ = [
    "VideoData", "load_video",
    "ROI", "save_rois", "load_rois", "select_rois_interactive",
    "GaborBank",
    "track_roi", "TrackResult",
    "amplitude_spectrum", "find_spectral_peaks",
    "half_power_damping", "log_decrement_damping", "stft_spectrogram",
    "scale_from_pixels", "scale_from_points",
    "CantileverBeam", "MATERIALS", "validate_frequency",
    "VibrometryPipeline", "PipelineConfig",
]
