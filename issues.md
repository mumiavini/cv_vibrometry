# Issues Log

Running log of bugs and performance issues found in this project (thesis
pipeline in `Code/vibrometry/`). Every issue is logged when found (`OPEN`)
and updated in place when fixed (`SOLVED`) — never delete an entry, append
the fix to it instead, so this stays a history of what broke and why.

Newest issue first.

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
