# vibrometry — Optical vibrometry pipeline (phase-based motion estimation)

Python implementation of the measurement pipeline described in the TCC
*"Vibrometria óptica aplicada para medição de vibrações em testes dinâmicos
de bancada"* (Trento, PUCPR). It extracts displacement signals from video of
a vibrating structure (the MVP: a clamped ruler with a high-contrast marker
at the free tip) and identifies its modal parameters.

## Module map (→ TCC section)

| Module | TCC section | Content |
|---|---|---|
| `video_io.py` | Importação dos quadros | grayscale frame stack `I(x,y,t_k)`, reference frame, Nyquist `F/2` |
| `roi.py` | Definição das regiões de interesse | measurement ROIs + static reference ROI, interactive selection, JSON persistence |
| `gabor.py` | Banco de filtros de Gabor e extração de fase | complex Gabor bank (eq. `gabor_kernel`), phase → displacement (eq. `fase_deslocamento`), amplitude-weighted least squares |
| `tracking.py` | — (practical extension) | coarse template matching + phase-based sub-pixel refinement |
| `spectral.py` | Extração de Parâmetros Modais | FFT with Hann window (eq. `fft`), peak picking, half-power ζ (eq. `zeta_halfpower`), logarithmic decrement ζ, STFT |
| `calibration.py` | Calibração Espacial | `s = d_ref / d_px` mm/pixel (eq. `escala`) |
| `beam.py` | Modelagem e Simulação | Euler–Bernoulli cantilever `f_n` (eq. `fn_cantilever`), `k_eq`, `m_eq`, mass loading (eq. `mass_loading`), 5 % validation criterion (eq. `criterio_validacao`) |
| `pipeline.py` | Arquitetura do Software | orchestration, reference-ROI compensation (eq. `compensacao`), export of figures / CSV / JSON |
| `synthetic.py` | Estratégia de Validação | synthetic free-decay video with exact ground truth for software verification |
| `run_analysis.py` | — | command-line entry point |

## Why "coarse + fine" tracking?

Pure phase-based estimation resolves displacements only up to half the filter
wavelength (`|δ| < λ/2`, a few pixels). A freely plucked ruler tip travels
tens of pixels per frame, so each ROI is first located with normalized
cross-correlation (integer pixel) and the Gabor phase difference then
provides the sub-pixel residual. For small-amplitude vibration the coarse
term stays at zero and the measurement reduces to the pure phase-based
method of the TCC.

## Quickstart

Run from the `Code/` directory with the project venv.

```bash
# software self-verification on a synthetic ground-truth video
python -m vibrometry.run_analysis --synthetic

# real video, interactive ROI selection (saves ROIs for reuse)
python -m vibrometry.run_analysis videos/ruler.mp4 --save-rois rois.json

# full analysis: saved ROIs, mm calibration, analytical validation
python -m vibrometry.run_analysis videos/ruler.mp4 --rois rois.json \
    --scale 0.45 --material steel --length 0.25 --width 0.026 --thickness 0.001

# faster/lower-memory run on a downscaled copy (see issues.md for the tradeoff)
python -m vibrometry.run_analysis videos/ruler.mp4 --rois rois.json \
    --scale 0.45 --resize-width 720
```

fps is auto-detected from the container and cross-checked against the
actual frame timestamps (catches a mislabeled/rounded fps tag); pass
`--fps` to override when this can't work, e.g. footage re-timestamped for
slow motion (240 fps captured, authored to play back at 30 fps) — the true
capture rate isn't recoverable from container timing in that case.

`--resize-width` downscales frames (aspect ratio preserved) before
tracking; `--scale` should always be the value measured at the video's
*original* resolution — it is rescaled automatically. ROIs saved with
`--save-rois` remember the frame size they were drawn on and are
auto-rescaled with a warning if loaded against a different `--resize-width`.

Outputs (PNG figures, `displacement_signals.csv`, `modal_results.json`) go to
`vibrometry/outputs/` by default.

See `demo.ipynb` for the same workflow as a notebook.

## Verification results (synthetic video, 30 fps, 12 s)

| Quantity | Imposed | Identified | Error |
|---|---|---|---|
| `f_n` | 2.500 Hz | 2.498 Hz | 0.09 % |
| ζ (log decrement) | 0.0120 | 0.0122 | ~2 % |
| tip displacement | — | RMS error 0.25 px over 58.6 px amplitude | ~0.4 % |

## Known limitations

* **Half-power ζ needs spectral resolution.** With a record of duration `T`
  the resolution is `1/T` Hz; if the true bandwidth `2ζf_n` is smaller, the
  Hann mainlobe dominates and ζ is overestimated (on the synthetic check it
  reads 0.025 instead of 0.012). For short free-decay records, prefer the
  logarithmic decrement value.
* **Nyquist.** Only frequencies below `F/2` are observable; record at 240 fps
  (1080p) when the expected `f_n` approaches 15 Hz of a 30 fps clip.
* **Rolling shutter / motion blur** (DJI Osmo Action 4): keep exposure
  ≤ 1/2000 s and RockSteady **off**, as established in the TCC methodology.
* **Texture.** ROIs need contrast in the Gabor band; use the printed marker
  on the tip and pick a textured static region for the reference ROI.

> **Note:** `Code/videos/video.mp4` currently in the repository is *not* the
> ruler recording (it is a puppy video). Place the actual experiment footage
> in `Code/videos/` and pass its path to `run_analysis`.
