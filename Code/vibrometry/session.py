"""
Session file (planejamento, section 7 "Arquivo de sessão"): every parameter
needed to reproduce the processing of one test run, saved as JSON
(``*.vibro.json``). Paths are stored relative to the session file when
possible so a session folder can be moved or shared.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from pathlib import Path

from .beam import CantileverBeam, MATERIALS
from .roi import ROI

SESSION_SUFFIX = ".vibro.json"
SESSION_VERSION = 1

# material code used in the file-naming convention
MATERIAL_CODES = {
    "steel": "aco",
    "polypropylene": "pp",
    "polystyrene": "ps",
    "aluminum_6351_t6": "al",
    "custom": "mat",
}

CHECKLIST = (
    "Câmera fixa no tripé de chão, de lado, a 0,3–0,6 m",
    "Foco, exposição e balanço de brancos travados; sem zoom",
    "Estabilização desligada",
    "Iluminação em corrente contínua ou constante",
    "Escala de 100 mm no plano do movimento",
    "Acelerômetro montado, alinhado e gravando",
    "Linha de base de 3 s com o sistema parado",
    "Batida seca + flash de LED (sincronismo)",
)


@dataclass
class SpecimenCfg:
    material: str = "steel"
    E_gpa: float = MATERIALS["steel"]["E"] / 1e9
    rho: float = MATERIALS["steel"]["rho"]
    L_mm: float = 300.0
    b_mm: float = 25.0
    t_mm: float = 1.0
    tip_mass_g: float = 0.0
    fps: float = 240.0
    oversampling: float = 10.0       # rule f_max <= fps / oversampling

    def beam(self) -> CantileverBeam:
        return CantileverBeam(self.L_mm / 1e3, self.b_mm / 1e3, self.t_mm / 1e3,
                              self.E_gpa * 1e9, self.rho)

    def predicted_f1(self) -> float:
        """f_n,1 including the tip mass (mass loading)."""
        beam = self.beam()
        return beam.mass_loaded_frequency(self.tip_mass_g / 1e3)


@dataclass
class MetaCfg:
    date: str = field(default_factory=lambda: date.today().strftime("%Y%m%d"))
    excitation_hz: float | None = None
    level: str = "A1"
    repetition: int = 1
    camera: str = "osmo"
    notes: str = ""
    checklist: list[bool] = field(default_factory=lambda: [False] * len(CHECKLIST))


@dataclass
class VideoCfg:
    path: str = ""
    fps_override: float | None = None
    start_s: float = 0.0
    end_s: float | None = None
    resize_width: int | None = None
    rois: list[dict] = field(default_factory=list)
    scale_mm_per_px: float | None = None
    calibration: dict | None = None  # {"p1": [x, y], "p2": [x, y], "length_mm": L}
    axis: str = "auto"
    compensate: bool = True
    wavelengths: list[float] = field(default_factory=lambda: [8.0, 16.0])
    search_margin: int = 60
    window: list[float] | None = None    # modal-analysis window [s]

    def roi_objects(self) -> list[ROI]:
        return [ROI(**d) for d in self.rois]


@dataclass
class AccelCfg:
    path: str = ""
    time_column: int | None = 0
    channel: int = 1
    fs: float | None = None
    unit: str = "g"
    sensitivity_mv_per_g: float = 100.0
    invert: bool = False
    integration: str = "frequency"       # "frequency" | "time"
    f_hp: float = 1.0
    f_lp: float | None = None
    window: list[float] | None = None    # accelerometer-clock window [s]


@dataclass
class CompareCfg:
    roi: str | None = None
    domain: str = "displacement"         # "displacement" | "acceleration"
    f_hp: float | None = 1.0             # band applied to both signals
    f_lp: float | None = None
    sync_mode: str = "impact"            # "impact" | "waveform" | "manual"
    offset_s: float = 0.0
    drift_ppm: float = 0.0
    window: list[float] | None = None    # video-time window [s]
    f_analysis: float | None = None      # None -> accelerometer's dominant
    crit_freq_pct: float = 1.0
    crit_amp_pct: float = 10.0
    crit_phase_deg: float = 10.0
    crit_eb_pct: float = 5.0
    crit_cv_pct: float = 5.0


def _from_dict(cls, d: dict | None):
    d = d or {}
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in names})


@dataclass
class Session:
    name: str = ""
    specimen: SpecimenCfg = field(default_factory=SpecimenCfg)
    meta: MetaCfg = field(default_factory=MetaCfg)
    video: VideoCfg = field(default_factory=VideoCfg)
    accel: AccelCfg = field(default_factory=AccelCfg)
    compare: CompareCfg = field(default_factory=CompareCfg)
    file: str = ""                       # where it was loaded from / saved to

    # ------------------------------------------------------------------ #
    def suggested_name(self) -> str:
        """AAAAMMDD_<material>_L<mm>_t<mm>_<f>Hz_A<nível>_r<n> (planejamento 7)."""
        s, m = self.specimen, self.meta

        def num(x: float) -> str:
            return f"{x:g}".replace(".", "p")

        parts = [m.date, MATERIAL_CODES.get(s.material, "mat"),
                 f"L{num(s.L_mm)}", f"t{num(s.t_mm)}"]
        parts.append(f"{num(m.excitation_hz)}Hz" if m.excitation_hz else "livre")
        if s.tip_mass_g:
            parts.append(f"m{num(s.tip_mass_g)}g")
        parts += [m.level, f"r{m.repetition}"]
        return "_".join(p for p in parts if p)

    def file_names(self) -> dict[str, str]:
        stem = self.name or self.suggested_name()
        return {
            "video": f"{stem}_{self.meta.camera}.mp4",
            "acelerometro": f"{stem}_acc.csv",
            "sessao": f"{stem}{SESSION_SUFFIX}",
        }

    @property
    def group(self) -> str:
        """Session name without the repetition tag, to pool repetitions."""
        return re.sub(r"_r\d+$", "", self.name) if self.name else ""

    # ------------------------------------------------------------------ #
    def to_dict(self, base: Path | None = None) -> dict:
        d = asdict(self)
        d.pop("file", None)
        d["version"] = SESSION_VERSION
        if base is not None:
            for key in ("video", "accel"):
                p = d[key]["path"]
                if p:
                    d[key]["path"] = _relative(p, base)
        return d

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        if not path.name.endswith(SESSION_SUFFIX):
            path = path.with_name(path.name.split(".")[0] + SESSION_SUFFIX)
        path.write_text(json.dumps(self.to_dict(path.parent), indent=2,
                                   ensure_ascii=False), encoding="utf-8")
        self.file = str(path)
        return path

    @classmethod
    def from_dict(cls, d: dict, base: Path | None = None) -> "Session":
        s = cls(
            name=d.get("name", ""),
            specimen=_from_dict(SpecimenCfg, d.get("specimen")),
            meta=_from_dict(MetaCfg, d.get("meta")),
            video=_from_dict(VideoCfg, d.get("video")),
            accel=_from_dict(AccelCfg, d.get("accel")),
            compare=_from_dict(CompareCfg, d.get("compare")),
        )
        if len(s.meta.checklist) != len(CHECKLIST):
            s.meta.checklist = (list(s.meta.checklist) + [False] * len(CHECKLIST))[
                : len(CHECKLIST)]
        if base is not None:
            for cfg in (s.video, s.accel):
                if cfg.path and not os.path.isabs(cfg.path):
                    cfg.path = str((base / cfg.path).resolve())
        return s

    @classmethod
    def load(cls, path: str | Path) -> "Session":
        path = Path(path)
        s = cls.from_dict(json.loads(path.read_text(encoding="utf-8")),
                          base=path.parent)
        s.file = str(path)
        return s


def _relative(p: str, base: Path) -> str:
    try:
        return os.path.relpath(p, base)
    except ValueError:              # different drive on Windows
        return p
