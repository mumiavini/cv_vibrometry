# Issues Log

Running log of bugs and performance issues found in this project (thesis
pipeline in `Code/vibrometry/`). Every issue is logged when found (`OPEN`)
and updated in place when fixed (`SOLVED`) — never delete an entry, append
the fix to it instead, so this stays a history of what broke and why.

Newest issue first.

---

## [OPEN] Bar near the joint moves as if the pivot were ≈ 24 mm behind the measured bearing axis

**Date opened:** 2026-10-31
**Area:** bench (joint/bearing), `Code/tools/forma_modal_multiponto.py`, `Code/sessions/k1_cm_acc.vibro.json`

**Symptom:** with the geometry measured from the bearing axis (L = 735, a = 655, x_a = 305 mm; the
calibration point p1 is the joint face, 15 mm from the axis, `calibration.x0_mm`), the multi-point
shape of `k1_cm_acc` fits the model well far from the root (≤ 1 % from 515 to 655 mm, MAC 0.9996) but
reads high close to it: +30 % at 65 mm, +14 % at 115 mm, +4 % at 215 mm. A line through the reliable
points crosses zero at x0 = −24 mm; the same line through the model's shape at those points crosses at
−4 mm (bending only). A separate track of the bar just outside the joint (≈ 40 mm) gives 1.45 mm against
≈ 1.0 mm for a pin at the axis, while the joint housing, the stand knob and the damper rod move
≤ 0.009 mm (noise floor, ≈ 5 µm).

**Root cause (not established):** the housing does not move, so it is not support motion. Either the
real rotation axis is ≈ 24 mm further from the tip than the point taken as "centre of the bearing"
(e.g. the bar is clamped in a fork that turns about a shaft further back), or the bar has play/slip
inside the joint. The tape positions and the image agree within ≤ 3 mm (scale fit 0.513 mm/px), so it is
not a calibration error. Effect on f₁: with the root moved to −24 mm the model gives 7.62 Hz instead of
7.69 Hz, inside the ±0.28 Hz model uncertainty (k dominates).

**Proposed fix (not yet implemented):** in the next takes put an ROI on the bar right at the joint and one
on the joint housing; photograph/measure the joint to locate the shaft axis; check bearing play (lift the
bar without the spring). If play is confirmed, model it as a vertical/rotational root spring.

---

## [SOLVED] Model predicted f₁ = 11.7 Hz for spring k₁ against 7.60 Hz measured

**Date opened:** 2026-10-25
**Date solved:** 2026-10-31
**Area:** `Code/sessions/k1_cm_acc.vibro.json` (specimen), `Code/vibrometry/beam.py` (`BeamFE`), bench

**Symptom:** the finite-element model of the pinned bar with the catalog spring (k₁ = 1500 N/m at
632 mm, 5 g accelerometer, no spring mass) predicted 11.70 Hz; PULSE measured 7.600 Hz and the video
7.763 Hz. The session carried a lumped "ferragem" of 383 g at 632 mm — the mass that would close the gap
with k = 1500 N/m — which was a fitted number, not a measurement (logged in `TODO.md`, "Discrepância").

**Root cause:** k and the effective mass are not separable from one frequency. Measured in the lab
(`Code/data/bancada/`): the **catalog stiffness was wrong** — static test k₁ = 857 ± 62 N/m (−43 %),
k₂ = 3291 ± 346 N/m (+32 %); spring k₁ 161 g (⅓ = 54 g in the model), bolt 36 g, nuts 10 g, so the
effective mass at the spring is 99.7 g, not 383 g. The geometry from the bearing axis is L = 735 mm,
a = 655 mm, x_a = 305 mm (not 720/632/300), and the bar weighs 644 g (ρ_eff = 2662 kg/m³). The spring
length readings were written as "mm" but are cm (in mm, k₁ ≈ 8.6 kN/m would give f₁ ≈ 24 Hz).

**Fix:** `vibrometry/springs.py` (`fit_spring_stiffness`, least squares with free intercept and standard
error), data in `Code/data/bancada/*.csv`, `tools/parametros_bancada.py` (fit, model, uncertainty
budget, figure → `Code/data/bancada/resultados/`). Session `k1_cm_acc` updated with the measured values
and `specimen.uncertainties`; `calibration.x0_mm = 15` records that p1 is the joint face (the scale
0.513 mm/px is unchanged). Model now: f₁ = 7.69 ± 0.28 Hz for k₁ (PULSE −1.2 %, video +0.9 %, both
within ±0.33 u) and 13.71 ± 0.72 Hz for k₂. Exports of `k1_cm_acc` (predicted f, mode-shape table,
`forma_modal/`, `incerteza/`) regenerated. Tests: `tests/test_springs.py`,
`tests/test_specimen_fe.py::test_repository_session_model_matches_the_measured_frequency`.

---

## [OPEN] Phase displacement has a gain bias when the ROI texture is not centred in the Gabor band

**Date opened:** 2026-10-25
**Area:** `Code/vibrometry/gabor.py` (`GaborBank.phase_displacement`), `Code/tests/test_subpixel_baseline.py`

**Symptom:** on synthetic textures with a known sub-pixel shift, the phase estimate had an RMS error of
≈ 0.045 px while the parabolic NCC peak gave ≈ 0.003 px; the error grows with the shift (a gain, not
noise). The test that assumed "phase beats NCC" failed and was replaced by honest tests (both beat
integer NCC by > 5×).

**Root cause:** each filter converts phase to displacement as Δφ / ω₀, with ω₀ the filter centre
frequency. The response of a broadband texture is dominated by the local spatial frequency of the
image inside the band, not by ω₀, so the estimate is scaled by ω_local / ω₀ (a few % to tens of %
depending on the texture).

**Proposed fix (not yet implemented as default):** `GaborBank(local_frequency=True)` (and
`TrackingParams.local_frequency`) divides by the amplitude-weighted local frequency
−ΣIm(C̄·∂C/∂u)/Σ|C|² of the reference response (falls back to ω₀ outside 0.25–4 ω₀). It reduces the
bias to < 0.6× in the synthetic tests (seeds 1–3). On the real video `k1_cm_acc` the amplitudes change
< 0.1 % and the static noise rises slightly (0.030 → 0.035 px), so it stays off by default; turn it on
for small-amplitude tests where the gain matters.

---

## [OPEN] ROIs on the smooth edge of the bar slide along the edge (aperture problem)

**Date opened:** 2026-10-25
**Area:** `Code/vibrometry/tracking.py` (`RoiTracker`), `Code/vibrometry/modeshape.py`,
`Code/tools/forma_modal_multiponto.py`

**Symptom:** ROIs placed along the bar for the multi-point mode shape (E5) gave nonsense amplitudes
and phase flips of 180° between neighbours; the automatic axis picked x, and even on y the coarse NCC
jumped. Final run: 9 of 15 points reliable; 250, 350, 400, 450, 680 and 710 mm fail the gate
(NCC ≥ 0.8 and sine-fit R² ≥ 0.9; minimum NCC 0.66–0.74, R² down to 0.45).

**Root cause:** a uniform straight edge has gradient only across it; along the edge every position
matches equally well, so the 2-D NCC search drifts sideways and the Gabor responses along the edge are
weak. Between ≈ 250 and 450 mm and near the tip the bar edge has no texture at all.

**Proposed fix (partly implemented):** `RoiTracker(search_axes="y")` restricts the coarse search to the
vertical axis (implemented, used by `track_points`), and the quality gate excludes unreliable points.
The real fix is in the bench: high-contrast markers every ≈ 50 mm along the bar
(`docs/roteiro_laboratorio.md`, section 3).

---

## [SOLVED] `BeamFE` snapped springs and masses to the nearest node

**Date opened:** 2026-10-25
**Date solved:** 2026-10-25
**Area:** `Code/vibrometry/beam.py` (`BeamFE._solve`), `Code/vibrometry/uncertainty.py`

**Symptom:** in the uncertainty propagation the sensitivities ∂f/∂x of spring and mass positions came
out exactly 0 (a ±2 mm perturbation does not move the node), and f₁ changed slightly with
`n_elements`.

**Root cause:** point springs/masses were added to the diagonal of the node closest to x
(`K[2·node, 2·node] += k`), so a position was only resolved to L / n_elements.

**Fix:** `BeamFE._point(x)` returns the DOFs and Hermite shape functions N of the element containing x,
and springs/masses enter as k·N·Nᵀ and m·N·Nᵀ. Positions now vary continuously; k₁ session f₁ =
7.602 Hz independent of the mesh; all `test_beam.py` tests pass unchanged.

---

## [SOLVED] Session saved on Windows does not load on Linux (backslash relative paths)

**Date opened:** 2026-10-25
**Date solved:** 2026-10-25
**Area:** `Code/vibrometry/session.py` (`Session.from_dict`, `_relative`)

**Symptom:** `Session.load("sessions/k1_cm_acc.vibro.json")` on Linux could not find the video:
the file stores `"..\\videos\\k1_cm_acc.mov"`, which POSIX reads as a single file name with
backslashes.

**Root cause:** relative paths were written with `str(Path)`, which uses `\` on Windows, and read back
without normalising separators.

**Fix:** `Session.from_dict` replaces `\` with `/` on POSIX before resolving relative paths, and
`_relative` saves with `Path.as_posix()` (forward slashes work on both systems). Regression test
`test_windows_style_relative_paths_resolve` in `Code/tests/test_specimen_fe.py`.

---

## [OPEN] Video and accelerometer of session `k1_cm_acc` are different takes and disagree on damping

**Date opened:** 2026-10-25
**Area:** `Code/sessions/k1_cm_acc.vibro.json`, `Code/videos/k1_cm_acc.mov`, `Code/data/acelerometro/`

**Symptom:** app comparison gave phase −117°, r = −0.35, amplitude −38 % (as pushed), and nothing
better after fixing the scale. With the scale fixed, video f_n = 7.763 Hz vs PULSE 7.600 Hz (+2.1 %,
above the 1 % criterion), and the decay differs by a factor ~7: video envelope σ = 0.049 1/s
(ζ ≈ 0.0010; envelope 20.5 → 15.3 m/s²-equivalent between t = 1 and 7 s) vs PULSE σ = 0.345 1/s
(ζ ≈ 0.0072; 19 → 2.4 m/s² in the same time).

**Root cause (partly established):** the file metadata say the video starts at 15/10/2026 20:22:39
(−03:00) and the PULSE record is stamped 15/10/2026 20:48:57 — 26 min apart, so they are separate
releases, not one event seen by two sensors (unless the lab PC clock is off). Phase, waveform overlay
and `sync_mode = impact` are therefore meaningless for this pair; only f_n, ζ and amplitude trends
can be compared. The 7× damping difference and the 2 % frequency difference are not explained yet
(different release, spring preload, damper blade position?).

**Proposed fix:** record video and PULSE simultaneously (impact + LED), and compare envelopes
(`vibrometry.reference`) before using waveform metrics; confirm the lab-PC clock.

**Update (2026-10-31):** with the measured spring and masses the model gives 7.69 ± 0.28 Hz, between the
two takes (PULSE −1.2 %, video +0.9 %); the 2.1 % gap between them is within the model uncertainty and
is still most likely take-to-take (new simultaneous takes pending). The damping difference is open.

---

## [OPEN] `curva_acelerometro_tempo_k1.csv` is a stroke trace, not a waveform

**Date opened:** 2026-10-25
**Area:** `Code/data/acelerometro/curva_acelerometro_tempo_k1.csv`, `vibrometry/accelerometer.py`

**Symptom:** double integration of the CSV (app step 3) gives a dominant frequency of 2.76 Hz with
`f_hp = 2 Hz`, or an amplitude 0.55 mm vs 7.6 mm of the video with `f_hp = 7.1 Hz`.

**Root cause:** 97 % of successive differences alternate in sign and ~47 % of the energy is at 50–100 Hz
(200 Hz series): the digitizer returned alternating upper/lower extremes of the vertical strokes of the
PULSE plot (the plot only has ~25.6 samples/s). The 6.5–9 Hz band still carries the right frequency
(7.606 Hz) but only ~35–55 % of the true amplitude, and the phase is not trustworthy.

**Fix applied:** documented in `Code/data/acelerometro/README.md`; use the envelope/spectrum
(`acc_k1_envelope_digitalizado.csv`, `vibrometry.reference`) as the reference instead.
Real fix: export the data from PULSE.

---

## [SOLVED] The app's analytical prediction (clamped Euler-Bernoulli) does not apply to the bench

**Date opened:** 2026-10-25
**Date solved:** 2026-10-25
**Area:** `Code/vibrometry/session.py` (`SpecimenCfg.predicted_f1`), `vibroapp` step 1 and 2

**Symptom:** predicted f₁ = 8.90 Hz (−12.8 % error) for the session as pushed, from placeholder
parameters (steel, L = 300 mm, t = 1 mm).

**Root cause:** the specimen section held the ruler placeholders, and the model is a clamped cantilever
with tip mass; the real system is an Al 6351-T6 bar pinned at a bearing, with a spring at 632 mm and the
accelerometer at 300 mm (`vibrometry.beam.BeamFE` handles this; the app does not use it yet).

**Proposed fix:** add a support type (clamped / pinned + springs + point masses, including spring
effective mass) to `SpecimenCfg` and use `BeamFE` in `predicted_f1`.

**Fix:** `SpecimenCfg` now has `support` (clamped / pinned / rotational), `root_stiffness`, `springs`
(x, k, spring mass, hardware) and `masses` (x, mass); `predicted_f1()` / `predicted_frequencies()` use the
finite-element model (`BeamFE`) whenever the closed form does not apply, with the spring effective mass
(⅓ of its mass + hardware). The planning page edits them (tables for springs and masses, warning when the
spring mass is missing), the report page and exports show the model and a mode-shape table
(`workflow.mode_shape_check`; ROI positions are set on the video page). Old sessions load unchanged.
Not done: the t-max / L-min solver of the planning page stays closed-form only (shown as "—" with
attachments, to keep the UI responsive).

---

## [SOLVED] Session `k1_cm_acc` had a wrong spatial scale, a stray analysis frequency and placeholder metadata

**Date opened:** 2026-10-25
**Date solved:** 2026-10-25
**Area:** `Code/sessions/k1_cm_acc.vibro.json`

**Symptom:** video displacement 7.2× too small (A = 1.05 mm, p2p 2.5 mm); comparison evaluated at
`f_analysis = 0.79 Hz`; predicted f₁ from a steel ruler; camera tagged "osmo", date 20261024.

**Root cause:** the calibration segment (p1 = (27.7, 512.2), p2 = (1430.6, 470.4), 1403.5 px) was the
whole free length of the bar but was entered as `length_mm = 100` → 0.07125 mm/px instead of
720 / 1403.5 = **0.5130 mm/px**. Checks that confirm 0.513: the screw hole (88 mm from the tip) falls at
(1430.6 − 1265) · 0.513 = 85 mm; the accelerometer ROI is 289 mm from p1 and 431 mm from p2 (measured:
300 and 430 mm); with the corrected scale the video acceleration-equivalent amplitude (ω²·A = 18 m/s²)
matches the PULSE envelope (17–19 m/s²).

**Fix:** calibration length 720 mm, scale 0.5130 mm/px, `f_analysis = null`, specimen = Al 6351-T6
720 × 25.4 × 12.7 mm, camera = iphone (iPhone 17e per file metadata), date = 20261015 (file metadata).
Original values: scale 0.07125, length 100, f_analysis 0.79, steel 300 × 25 × 1 mm.

---

## [OPEN] 91 MB video tracked in git

**Date opened:** 2026-10-25
**Area:** `Code/videos/k1_cm_acc.mov`

**Symptom:** the file is 91 MB; GitHub warns above 50 MB and rejects above 100 MB, so the next video
cannot be pushed.

**Mitigation done:** `Code/videos/*` is git-ignored (except the two tracked files); the history still
carries the 91 MB blob. **Proposed fix:** Git LFS or external storage with SHA-256 in a manifest.

---

## [OPEN] Full-video batch processing is too slow for real-time use

**Date opened:** 2026-09-03
**Area:** `Code/vibrometry/video_io.py`, `tracking.py`, `spectral.py`

**Symptom:** Running `run_analysis` on a full-length real clip (e.g.
`video longo cortato.mp4`, 1080x1920, 4515 frames / 150 s) takes a long time
to complete.

**Root cause:** the pipeline is architected as an offline batch process, not
a stream:
- `video_io.load_video` decodes and holds the *entire* video as an in-memory
  grayscale frame stack before any analysis starts (~9 GB for this clip).
- `tracking.track_roi` runs a plain Python `for` loop over every frame, doing
  one NCC template match + 16 Gabor filter convolutions (8 filters x
  real/imag) per frame per ROI — no vectorization across time.
- Spectral analysis (FFT/STFT) only runs after the full displacement time
  series has been collected; nothing is incremental.

Cost scales linearly with total frames submitted, regardless of how much of
the clip is actually informative (a 150 s clip may contain only a few
seconds of useful pluck+decay).

**Proposed fix (not yet implemented):**
- Stream frames one at a time (process-and-discard) instead of loading the
  whole video into memory.
- Replace the end-of-record FFT with an incremental / sliding-window STFT.
- Shrink the Gabor filter bank and/or operate only on ROI crops.
- Trim input to the segment of interest before analysis in the meantime.

**Partial mitigation implemented (2026-09-03): `--resize-width`.**
`video_io.load_video` now accepts `resize_width` (CLI: `--resize-width`),
downscaling frames with `cv2.resize` (`INTER_AREA`) before stacking and
tracking. This cuts memory and per-frame NCC/Gabor cost, but does **not**
fix the underlying batch/streaming architecture above — it only shrinks the
constant factor, the cost is still O(n_frames). Confirmed on the real
`video longo cortato.mp4` clip at `--resize-width 720`: still took several
minutes end to end, i.e. this alone is not sufficient for real-time.

Tradeoff of downscaling:
- Sub-pixel tracking precision is roughly constant *in pixels* (~0.1-0.3 px
  RMS, per the synthetic verification), not in physical units. Downscaling
  by factor `r` increases the effective mm/pixel scale by `1/r`, so the same
  pixel-domain noise represents proportionally more real-world error (e.g.
  720p from 1080x1920 -> `r ~= 0.667` -> ~1.5x more mm error for the same
  pixel noise).
- Whether that matters depends on how many pixels the ROI/marker occupies
  before resizing. Checked against this project's saved ROI
  (`Code/vibrometry/rois.json`: marker 396x286 px, reference 127x115 px on
  the 1080x1920 clip) — even at 720p (~264x191 / 85x77 px) there's ample
  margin over the Gabor bank's 8-16 px wavelengths, so texture resolution is
  not the limiting factor for this marker; only the mm/pixel error growth
  applies, and it is likely small versus cm-scale vibration amplitude.
- `run_analysis.py` auto-adjusts `--scale` for the resize factor, so users
  always supply mm/px measured at the video's *original* resolution.
- ROIs saved via `--save-rois` are now tagged with the frame size they were
  drawn on (`roi.save_rois`/`load_rois`) and auto-rescaled, with a printed
  warning, if reused at a different `--resize-width` — otherwise a saved ROI
  would silently point at the wrong region after a resolution change.

**Partial mitigation implemented (2026-10-08): streaming tracker + FFT
Gabor bank.** Two of the proposed items are done for the desktop app /
batch path (`workflow.run_video` → `streaming.track_video`):
- *No full frame stack in memory.* `tracking.RoiTracker` tracks one frame at
  a time (`update(frame)`); `streaming.track_video` feeds it while decoding,
  so memory no longer grows with clip length. `track_roi` is now a thin
  wrapper over `RoiTracker`, same results.
- *Cheaper Gabor stage.* Profiling showed 86 % of the time in
  `cv2.filter2D` (16 calls per ROI per frame, 55×55 kernels, and OpenCV
  recomputes the kernel DFT on every call). `GaborBank.responses` now does
  one FFT of the zero-padded patch and multiplies by cached kernel spectra
  (`scipy.fft`, `next_fast_len`, complex64). Results are identical in the
  interior used by `phase_displacement` (relative error ~3e-7; covered by
  `tests/test_tracking_physics.py`); 13.2 ms → 1.8 ms per 104×130 patch.
- Measured end to end: synthetic 640×360 / 240 fps clip, 2 ROIs, 1920
  frames: 52.5 s → 9.1 s (~210 frames/s). Real `video low res.LRF`
  (825 frames, 720×1280, resized to 360 wide): 17.9 s.

Still OPEN: cost remains O(n_frames) and fully offline (no incremental /
sliding STFT), and the legacy CLI `run_analysis` still goes through
`video_io.load_video` (whole clip in memory).

---

## [SOLVED] fps trusted the container tag with no cross-check against actual frame timing

**Date opened:** 2026-09-03
**Date solved:** 2026-09-03
**Area:** `Code/vibrometry/video_io.py` (`load_video`)

**Symptom:** `load_video` used `cap.get(cv2.CAP_PROP_FPS)` unconditionally
whenever `--fps` wasn't passed. A wrong or rounded fps tag (known DJI Osmo
Action 4 gotcha: 240 fps footage sometimes tagged for 30 fps playback, or
just a bad/rounded metadata tag) would silently propagate into every derived
quantity — Nyquist frequency, `f_n`, damping — with no warning.

**Root cause:** no cross-check existed between the container's declared
average-fps tag and the actual per-frame timestamps embedded in the file.

**Fix:** added `_measure_fps()` in `video_io.py`: seeks to the last frame
and computes fps from the elapsed timestamp between frame 0 and frame
`n-1`, independent of the container's average-fps tag. If it disagrees with
the declared tag by more than 2%, the measured value is used automatically
and a warning is printed; an explicit `--fps` always overrides both.
`VideoData.fps_source` records which was used (`container` / `measured` /
`override`) and is surfaced in `pipeline.report()` and `modal_results.json`.
Verified against all 4 real clips in `Code/videos/` — declared and measured
agreed within ~0.1% on each, so no false positives on this footage.

**Caveat:** this cannot recover the true capture rate of footage that was
*intentionally* re-timestamped for slow motion (e.g. 240 fps captured but
authored so playback timestamps read 30 fps) — the real rate isn't present
in standard container timing at all in that case; `--fps` override is still
required then.

---

## [SOLVED] `pipeline.export()` crashes with `TypeError: Object of type bool is not JSON serializable`

**Date opened:** 2026-09-03
**Date solved:** 2026-09-03
**Area:** `Code/vibrometry/beam.py` (`validate_frequency`)

**Symptom:** Running `run_analysis` with `--material`/`--length`/`--width`/
`--thickness` (i.e. with an analytical beam model attached, so
`validate_frequency` runs) crashed inside `pipeline.export()` while writing
`modal_results.json`.

**Root cause:** numpy >= 2.0 renamed `numpy.bool_`'s class name to `"bool"`,
but it still is not a subclass of Python's built-in `bool`.
`validate_frequency` computed `passed=error < tolerance_percent`, producing
a `numpy.bool_` (and numpy floats for the other fields) that `json.dumps`
rejects.

**Fix:** cast `f_measured`, `f_analytical`, `error_percent` to
`float(...)` and `passed` to `bool(...)` before constructing
`ValidationResult`. Commit `1e41723` on `main` (cherry-picked from `f194de8`
on branch `worktree-cosmic-wiggling-parnas`).
