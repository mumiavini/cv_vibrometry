"""
Command-line entry point for the optical vibrometry pipeline.

Examples (run from the Code/ directory):

  # interactive ROI selection, results in pixels
  python -m vibrometry.run_analysis videos/ruler.mp4

  # saved ROIs + spatial calibration + analytical validation (steel ruler)
  python -m vibrometry.run_analysis videos/ruler.mp4 --rois rois.json \
      --scale 0.45 --material steel --length 0.25 --width 0.026 \
      --thickness 0.001

  # self-verification on a synthetic video with known ground truth
  python -m vibrometry.run_analysis --synthetic
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .beam import CantileverBeam, MATERIALS
from .pipeline import PipelineConfig, VibrometryPipeline
from .roi import ROI, load_rois, save_rois, select_rois_interactive
from .video_io import load_video


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vibrometry",
        description="Phase-based optical vibrometry of a cantilever beam.",
    )
    p.add_argument("video", nargs="?", help="path to the recorded video")
    p.add_argument("--rois", help="JSON file with saved ROIs; if omitted, "
                                  "ROIs are selected interactively")
    p.add_argument("--save-rois", help="save the interactively selected ROIs "
                                       "to this JSON file")
    p.add_argument("--out", default="vibrometry/outputs",
                   help="output directory (default: %(default)s)")
    p.add_argument("--fps", type=float,
                   help="override the container fps (high-frame-rate footage)")
    p.add_argument("--scale", type=float,
                   help="spatial calibration s [mm/pixel] (eq:escala)")
    p.add_argument("--axis", choices=("x", "y", "auto"), default="auto",
                   help="displacement component to analyse")

    g = p.add_argument_group("analytical cantilever model (validation)")
    g.add_argument("--material", choices=sorted(MATERIALS),
                   help="ruler material preset")
    g.add_argument("--length", type=float, help="free length L [m]")
    g.add_argument("--width", type=float, help="cross-section width b [m]")
    g.add_argument("--thickness", type=float,
                   help="cross-section thickness h [m]")

    p.add_argument("--synthetic", action="store_true",
                   help="generate a synthetic ground-truth video and run the "
                        "pipeline on it (software verification)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out)

    beam = None
    if args.material:
        missing = [n for n in ("length", "width", "thickness")
                   if getattr(args, n) is None]
        if missing:
            raise SystemExit(
                f"--material requires --{', --'.join(missing)}"
            )
        beam = CantileverBeam.from_material(
            args.length, args.width, args.thickness, args.material
        )

    if args.synthetic:
        from .synthetic import generate_cantilever_video

        video_path = out_dir / "synthetic_cantilever.mp4"
        out_dir.mkdir(parents=True, exist_ok=True)
        truth = generate_cantilever_video(video_path)
        print(f"Synthetic video written to {video_path}")
        print(f"  ground truth: f_d = {truth.f_d:.3f} Hz, "
              f"zeta = {truth.zeta:.4f}")

        tx, ty = truth.marker_center
        r = truth.marker_radius + 14
        sx, sy = truth.static_marker_center
        rois = [
            ROI("tip", tx - r, ty - r, 2 * r, 2 * r),
            ROI("reference", sx - 26, sy - 26, 52, 52, is_reference=True),
        ]
        video = load_video(video_path)
    else:
        if not args.video:
            raise SystemExit("Provide a video path or use --synthetic.")
        video = load_video(args.video, fps_override=args.fps)
        if args.rois:
            rois = load_rois(args.rois)
        else:
            print("Select the measurement ROIs, then the reference ROI...")
            rois = select_rois_interactive(video.reference_frame)
            if not rois:
                raise SystemExit("No ROI selected.")
            if args.save_rois:
                save_rois(rois, args.save_rois)
                print(f"ROIs saved to {args.save_rois}")

    config = PipelineConfig(
        scale_mm_per_px=args.scale,
        beam=beam,
        axis=args.axis,
    )
    pipeline = VibrometryPipeline(video, rois, config)
    pipeline.run()
    print()
    print(pipeline.report())

    saved = pipeline.export(out_dir)
    print(f"\nFigures and data exported to {saved.resolve()}")

    if args.synthetic:
        modal = pipeline.modal_results[0]
        err = abs(modal.f_n - truth.f_d) / truth.f_d * 100.0
        print(f"\nSelf-verification: identified {modal.f_n:.3f} Hz vs "
              f"imposed {truth.f_d:.3f} Hz -> error {err:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
