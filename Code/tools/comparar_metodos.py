"""
E1 — comparação do estágio sub-pixel: fase (Gabor) × correlação simples.

Rastreia o vídeo de uma sessão com cada método (mesmas ROIs, mesma referência,
mesma calibração) e grava tabela, JSON e figura em
``<sessão>_resultados/comparacao_metodos/``.

Uso (a partir de Code/):  python -m tools.comparar_metodos sessions/k1_cm_acc.vibro.json
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from vibrometry.baseline import (  # noqa: E402
    METHOD_LABELS, compare_subpixel_methods, consistency, static_pair_noise)
from vibrometry.roi import ROI  # noqa: E402
from vibrometry.session import SESSION_SUFFIX, Session  # noqa: E402
from vibrometry.spectral import amplitude_spectrum  # noqa: E402


def out_dir(session_path: Path) -> Path:
    stem = session_path.name.removesuffix(SESSION_SUFFIX)
    d = session_path.parent / f"{stem}_resultados" / "comparacao_metodos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    path = Path(argv[0])
    s = Session.load(path)
    res = compare_subpixel_methods(
        s, progress=lambda m, i, n: print(f"\r{m}: {i}/{n}", end="", flush=True) if i % 400 == 0 else None)
    print()
    out = out_dir(path)
    cons = consistency(res)
    rows = []
    for m, r in res.items():
        for roi, mt in r.metrics.items():
            rows.append({"metodo": m, "roi": roi, **asdict(mt),
                         "ruido_referencia_px": r.reference_noise_px,
                         "dif_rms_vs_fase": cons.get(m, {}).get(roi)})
    # noise from two static wall regions (camera motion cancels in the difference)
    wa = ROI("parede_A", 700, 600, 150, 110)
    wb = ROI("parede_B", 1100, 810, 150, 110)
    print("ruído estático (duas ROIs na parede)...")
    static = static_pair_noise(s, wa, wb)
    (out / "comparacao_metodos.json").write_text(
        json.dumps({"sessao": s.name, "unidade": next(iter(res.values())).unit,
                    "linhas": rows,
                    "ruido_estatico_px": {"rois": [asdict(wa), asdict(wb)], **static}},
                   indent=2, ensure_ascii=False), encoding="utf-8")

    # table (markdown) for quick reading
    unit = next(iter(res.values())).unit
    noise_unit = "µm" if unit == "mm" else f"10⁻³ {unit}"
    lines = [f"| Método | ROI | f (Hz) | A ({unit}) | ζ (envoltória) | ruído ({noise_unit}) | SNR (dB) | ruído ref. (px) | dif. RMS × fase ({unit}) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        def g(k, fmt):
            v = r[k]
            return "—" if v is None else format(v, fmt)
        nf = "—" if r["noise_floor"] is None else f"{r['noise_floor'] * 1e3:.2f}"
        lines.append(f"| {METHOD_LABELS[r['metodo']]} | {r['roi']} | {g('f_n', '.4f')} | "
                     f"{g('amplitude', '.3f')} | {g('zeta', '.5f')} | {nf} | {g('snr_db', '.1f')} | "
                     f"{g('ruido_referencia_px', '.3f')} | {g('dif_rms_vs_fase', '.4f')} |")
    lines += ["", "Ruído de uma ROI estática (diferença entre duas regiões da parede, ÷√2, sem tendência):", "",
              "| Método | σ_x (px) | σ_y (px) | σ_y (mm) |", "|---|---|---|---|"]
    sc = s.video.scale_mm_per_px or float("nan")
    for m, v in static.items():
        lines.append(f"| {METHOD_LABELS[m]} | {v['std_x_px']:.4f} | {v['std_y_px']:.4f} | {v['std_y_px'] * sc:.4f} |")
    (out / "comparacao_metodos.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    # figure: detail of the signals and spectra of the first measurement ROI
    roi = next(iter(res["phase"].signals))
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    t = res["phase"].times
    sel = (t >= 2.0) & (t <= 2.4)
    for m, r in res.items():
        x = r.signals[roi] - np.mean(r.signals[roi])
        ax[0].plot(t[sel], x[sel], label=METHOD_LABELS[m], lw=1.2)
        f, a = amplitude_spectrum(x, 1.0 / (t[1] - t[0]))
        ax[1].semilogy(f, a, label=METHOD_LABELS[m], lw=0.9)
    ax[0].set_xlabel("tempo [s]"); ax[0].set_ylabel(f"deslocamento [{unit}]")
    ax[0].set_title(f"{roi}: detalhe (2,0–2,4 s)")
    ax[1].set_xlim(0, 120); ax[1].set_xlabel("frequência [Hz]")
    ax[1].set_ylabel(f"amplitude [{unit}]"); ax[1].set_title("espectro")
    for a_ in ax:
        a_.grid(alpha=0.3)
    ax[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "fig_comparacao_metodos.png", dpi=170)
    print(f"resultados em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
