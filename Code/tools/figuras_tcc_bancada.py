"""
Figuras do TCC para a campanha de bancada (29/10/2026) a partir do que o
aplicativo exportou, sem o vídeo:

* ``fig_bancada_rois.png``: quadro de referência com as ROIs, refeito a partir
  de ``fig_rois.png`` da sessão (os rótulos exportados se sobrepõem quando as
  ROIs estão próximas). O quadro é recuperado removendo os desenhos coloridos
  (rótulos e retângulos) por *inpainting* e as ROIs são redesenhadas com as
  coordenadas da sessão;
* ``fig_bancada_espectrograma.png``: cópia do espectrograma exportado da ROI
  do parafuso.

Executar a partir de Code/:
    python -m tools.figuras_tcc_bancada [sessions/<sessão>.vibro.json]
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from vibrometry.session import SESSION_SUFFIX, roi_key  # noqa: E402

IMAGES = Path(__file__).resolve().parents[2] / "Book" / "Images"
DEFAULT = Path("sessions/20261030_al_L735_k1_r2.vibro.json")
LABELS = {  # nome na sessão -> rótulo na figura
    "acelerometro": "Acelerômetro (305 mm)",
    "parafuso": "Parafuso da mola (655 mm)",
    "pontoaleatoriomarcado": "Marca de fita (≈ 348 mm)",
    "pontoaleatorioliso": "Borda lisa",
    "parede": "Referência (parede)",
}


def recover_frame(fig_png: Path, rois: list[dict], size=(1920, 1080)) -> np.ndarray:
    """Grayscale frame behind the exported ROI figure: locate the image area
    from two ROI rectangles, crop, and inpaint the coloured overlay."""
    img = cv2.imread(str(fig_png), cv2.IMREAD_COLOR)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    colour = (hsv[..., 1] > 60).astype(np.uint8)          # rótulos e retângulos
    # the ROI rectangles are the saturated blobs; use the leftmost/rightmost
    # measurement ROI to get the image scale and offset in the figure
    blue = ((hsv[..., 1] > 60) & (hsv[..., 0] > 90) & (hsv[..., 0] < 130)).astype(np.uint8)
    meas = [r for r in rois if not r.get("is_reference")]
    left = min(meas, key=lambda r: r["x"])
    right = max(meas, key=lambda r: r["x"] + r["w"])

    def longest_run(v: np.ndarray) -> tuple[int, int]:
        e = np.flatnonzero(np.diff(np.r_[0, v.astype(int), 0]))
        if not e.size:
            return 0, 0
        runs = list(zip(e[::2], e[1::2]))
        return max(runs, key=lambda ab: ab[1] - ab[0])

    # vertical box edges are long blue runs; label glyphs are short. The
    # first guess of the scale comes from the figure width (image ~97 %).
    s0 = 0.97 * img.shape[1] / 1920
    min_run = 0.8 * min(left["h"], right["h"]) * s0
    cols = [x for x in range(blue.shape[1])
            if np.diff(longest_run(blue[:, x]))[0] >= min_run]
    x_min, x_max = min(cols), max(cols)
    s = (x_max - x_min + 1) / ((right["x"] + right["w"]) - left["x"])
    x0 = x_min - left["x"] * s
    top = longest_run(blue[:, x_min])[0]
    y0 = top - left["y"] * s
    w, h = size
    crop = img[int(round(y0)):int(round(y0 + h * s)), int(round(x0)):int(round(x0 + w * s))]
    mask = cv2.dilate(colour, np.ones((5, 5), np.uint8))
    mask = mask[int(round(y0)):int(round(y0 + h * s)), int(round(x0)):int(round(x0 + w * s))]
    clean = cv2.inpaint(crop, mask, 5, cv2.INPAINT_TELEA)
    return cv2.cvtColor(cv2.resize(clean, size, interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2GRAY)


def fig_rois(frame: np.ndarray, rois: list[dict], out: Path) -> None:
    x_lo, x_hi, y_lo, y_hi = 430, 1640, 300, 960
    fig, ax = plt.subplots(figsize=(7.0, 7.0 * (y_hi - y_lo) / (x_hi - x_lo)))
    ax.imshow(frame, cmap="gray", vmin=0, vmax=255)
    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(y_hi, y_lo)
    ax.axis("off")
    # label anchors (text positions), spread above the bar
    text_pos = {
        "acelerometro": (700, 340), "pontoaleatoriomarcado": (900, 395),
        "pontoaleatorioliso": (1130, 345), "parafuso": (1440, 395), "parede": (960, 700),
    }
    for r in rois:
        k = roi_key(r["name"])
        colour = "tab:orange" if r.get("is_reference") else "tab:cyan"
        ax.add_patch(Rectangle((r["x"], r["y"]), r["w"], r["h"], fill=False, lw=1.6, ec=colour))
        tx, ty = text_pos.get(k, (r["x"], r["y"] - 30))
        ax.annotate(LABELS.get(k, r["name"]), xy=(r["x"] + r["w"] / 2, r["y"]),
                    xytext=(tx, ty), fontsize=8, color="black", ha="center",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=colour, lw=1),
                    arrowprops=dict(arrowstyle="-", color=colour, lw=1))
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    session = Path(argv[0]) if argv else DEFAULT
    res = session.parent / f"{session.name.removesuffix(SESSION_SUFFIX)}_resultados"
    rois = json.loads(session.read_text(encoding="utf-8"))["video"]["rois"]
    frame = recover_frame(res / "fig_rois.png", rois)
    fig_rois(frame, rois, IMAGES / "fig_bancada_rois.png")
    shutil.copyfile(res / "fig_espectrograma_Parafuso.png", IMAGES / "fig_bancada_espectrograma.png")
    print(IMAGES / "fig_bancada_rois.png", IMAGES / "fig_bancada_espectrograma.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
