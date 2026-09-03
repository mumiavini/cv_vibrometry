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
