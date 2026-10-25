"""
Reference accelerometer: file import, unit conversion and conversion to
displacement (planejamento, section 8 item 8; TCC "Ensaio comparativo com
acelerômetro piezoelétrico").

Displacement is obtained by double integration in the frequency domain,

    X(f) = A(f) / (j 2 pi f)^2 = -A(f) / (2 pi f)^2,

with linear detrending after each integration and a smooth high-pass below
``f_hp`` (the 1/f^2 gain would otherwise blow up offset, drift and
low-frequency noise); see ``frequency_integrate``. A time-domain alternative
(high-pass + trapezoidal integration, twice) is also provided. The naive
double integration without filtering is deliberately not offered.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import fft as sfft
from scipy import signal as ss
from scipy.integrate import cumulative_trapezoid

G = 9.80665  # standard gravity [m/s^2]

# unit -> factor to m/s^2 (voltage units use the sensitivity, see to_si)
UNITS = ("g", "m/s²", "mm/s²", "mV", "V")


# --------------------------------------------------------------------------- #
# file import
# --------------------------------------------------------------------------- #
@dataclass
class TableData:
    """Numeric table read from a CSV/TXT export."""

    path: str
    columns: list[str]
    data: np.ndarray            # (n_rows, n_cols) float, NaN where not numeric
    delimiter: str              # "" means whitespace
    decimal: str
    header_lines: int
    preview: list[str]          # first lines of the file, for display


def _decode(raw: bytes) -> tuple[str, str]:
    """(text, encoding name usable by pandas)."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8"), "utf-8-sig"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("latin-1"), "latin-1"


def _split(line: str, delim: str) -> list[str]:
    parts = line.split() if delim == "" else line.split(delim)
    return [p.strip().strip('"').strip("'") for p in parts]


def _is_number(s: str, dec: str) -> bool:
    if dec == ",":
        if "." in s:
            return False
        s = s.replace(",", ".")
    try:
        float(s)
        return True
    except ValueError:
        return False


# (delimiter, decimal); "." variants first so they win ties
_CANDIDATES = [(";", "."), ("\t", "."), (",", "."), ("", "."),
               (";", ","), ("\t", ","), ("", ",")]


def read_table(path: str | Path) -> TableData:
    """Read a delimited text export (CSV/TXT, e.g. from Dewesoft).

    Delimiter (``;``, tab, ``,`` or whitespace), decimal separator (``.`` or
    ``,``) and the header block are detected automatically. The column names
    are taken from the last non-numeric line(s) above the data.
    """
    path = str(path)
    text, encoding = _decode(Path(path).read_bytes())
    lines = text.splitlines()
    non_empty = [ln for ln in lines if ln.strip()]
    if not non_empty:
        raise ValueError("Arquivo vazio.")
    sample = non_empty[-300:] if len(non_empty) > 300 else non_empty

    best, best_score = None, (-1.0, -1)
    for delim, dec in _CANDIDATES:
        rows = [_split(ln, delim) for ln in sample]
        n_fields = Counter(len(r) for r in rows).most_common(1)[0][0]
        if delim == "," and dec == ",":
            continue
        good = [r for r in rows if len(r) == n_fields]
        numeric = sum(_is_number(c, dec) for r in good for c in r)
        frac = numeric / max(1, len(good) * n_fields)
        score = (round(frac * len(good) / len(rows), 3), n_fields)
        if score > best_score:
            best, best_score = (delim, dec, n_fields), score
    if best is None or best_score[0] < 0.5:
        raise ValueError("Não foi possível identificar colunas numéricas.")
    delim, dec, n_fields = best

    # data = trailing block of lines with n_fields numeric fields (walking
    # back from the end, so metadata such as "Sample rate;1000" in the header
    # is not mistaken for data); relaxed to n_fields-1 numeric fields when
    # one column is not numeric (e.g. a clock-time stamp)
    def data_start(min_numeric: int) -> int:
        start = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if not lines[i].strip():
                continue
            r = _split(lines[i], delim)
            if (len(r) == n_fields
                    and sum(_is_number(c, dec) for c in r) >= min_numeric):
                start = i
            else:
                break
        return start

    start = data_start(n_fields)
    if len(lines) - start < 4 and n_fields > 1:
        start = data_start(n_fields - 1)
    if start >= len(lines):
        raise ValueError("Não foi possível identificar o bloco de dados.")

    header = [ln for ln in lines[:start] if ln.strip()]
    names = None
    named = [_split(ln, delim) for ln in header[-2:]]
    named = [r for r in named if len(r) == n_fields]
    if named:
        names = named[-1]
        if len(named) == 2 and all(re.fullmatch(r"\[?.{0,12}\]?", u) for u in named[1]):
            # second line looks like a units row: "Name [unit]"
            names = [f"{a} [{b.strip('[]')}]" if b else a
                     for a, b in zip(named[0], named[1])]
    if names is None or not any(names):
        names = [f"Coluna {i + 1}" for i in range(n_fields)]
    names = [n if n else f"Coluna {i + 1}" for i, n in enumerate(names)]

    df = pd.read_csv(
        path,
        sep=r"\s+" if delim == "" else delim,
        decimal=dec,
        skiprows=start,
        header=None,
        engine="python" if delim == "" else "c",
        on_bad_lines="skip",
        encoding=encoding,
        skip_blank_lines=True,
    )
    df = df.iloc[:, :n_fields].apply(pd.to_numeric, errors="coerce")
    return TableData(
        path=path,
        columns=names,
        data=df.to_numpy(dtype=float),
        delimiter=delim,
        decimal=dec,
        header_lines=start,
        preview=lines[: min(len(lines), start + 6)],
    )


def guess_columns(table: TableData) -> tuple[int | None, int]:
    """(time column or None, first acceleration channel) by column name."""
    time_col = None
    for i, name in enumerate(table.columns):
        if re.search(r"\b(time|tempo|t)\b|\[s\]|\(s\)", name, re.IGNORECASE):
            time_col = i
            break
    if time_col is None and table.data.shape[1] > 1:
        col = table.data[:, 0]
        d = np.diff(col[np.isfinite(col)])
        if d.size > 2 and np.all(d > 0):
            time_col = 0
    channel = next(
        (i for i in range(table.data.shape[1]) if i != time_col), 0)
    return time_col, channel


def guess_unit(name: str) -> str:
    n = name.lower()
    if "mm/s" in n:
        return "mm/s²"
    if "m/s" in n:
        return "m/s²"
    if "[mv]" in n or "(mv)" in n:
        return "mV"
    if "[v]" in n or "(v)" in n:
        return "V"
    return "g"


# --------------------------------------------------------------------------- #
# record
# --------------------------------------------------------------------------- #
@dataclass
class AccelSettings:
    time_column: int | None = 0          # None -> uniform at ``fs``
    channel: int = 1
    fs: float | None = None              # required without a time column
    unit: str = "g"
    sensitivity_mv_per_g: float = 100.0  # only for mV / V units
    invert: bool = False                 # flips the measuring axis


@dataclass
class AccelRecord:
    t: np.ndarray            # uniform time [s] on the accelerometer clock
    a: np.ndarray            # acceleration [m/s^2], mean removed
    fs: float                # sampling rate [Hz]
    label: str
    resampled: bool          # True if the time column was not uniform
    jitter_percent: float    # std of dt / mean dt, before resampling

    @property
    def duration(self) -> float:
        return self.t[-1] - self.t[0] if self.t.size > 1 else 0.0


def to_si(values: np.ndarray, unit: str, sensitivity_mv_per_g: float) -> np.ndarray:
    """Convert raw values to m/s^2."""
    if unit == "g":
        return values * G
    if unit == "m/s²":
        return values
    if unit == "mm/s²":
        return values * 1e-3
    if unit == "mV":
        return values / sensitivity_mv_per_g * G
    if unit == "V":
        return values * 1e3 / sensitivity_mv_per_g * G
    raise ValueError(f"Unidade desconhecida: {unit}")


def build_record(table: TableData, cfg: AccelSettings) -> AccelRecord:
    data = table.data
    if not 0 <= cfg.channel < data.shape[1]:
        raise ValueError("Canal inválido.")
    a_raw = data[:, cfg.channel]

    if cfg.time_column is not None:
        t_raw = data[:, cfg.time_column]
        ok = np.isfinite(t_raw) & np.isfinite(a_raw)
        t_raw, a_raw = t_raw[ok], a_raw[ok]
        if t_raw.size < 4:
            raise ValueError("Coluna de tempo sem valores numéricos.")
        order = np.argsort(t_raw, kind="stable")
        t_raw, a_raw = t_raw[order], a_raw[order]
        keep = np.concatenate([[True], np.diff(t_raw) > 0])
        t_raw, a_raw = t_raw[keep], a_raw[keep]
        dt = np.diff(t_raw)
        fs = cfg.fs or 1.0 / np.median(dt)
        jitter = float(100.0 * dt.std() / dt.mean())
        resampled = jitter > 0.5 or cfg.fs is not None
        if resampled:   # onto a uniform grid at fs
            n = int(np.floor((t_raw[-1] - t_raw[0]) * fs)) + 1
            t = t_raw[0] + np.arange(n) / fs
            a = np.interp(t, t_raw, a_raw)
        else:
            t, a = t_raw, a_raw
    else:
        if not cfg.fs:
            raise ValueError("Sem coluna de tempo: informe a taxa de amostragem.")
        a = a_raw[np.isfinite(a_raw)]
        fs = cfg.fs
        t = np.arange(a.size) / fs
        resampled, jitter = False, 0.0

    a = to_si(np.asarray(a, dtype=float), cfg.unit, cfg.sensitivity_mv_per_g)
    a = a - a.mean()            # gravity / sensor offset
    if cfg.invert:
        a = -a
    return AccelRecord(t=np.asarray(t, dtype=float), a=a, fs=float(fs),
                       label=table.columns[cfg.channel],
                       resampled=resampled, jitter_percent=jitter)


# --------------------------------------------------------------------------- #
# integration / differentiation
# --------------------------------------------------------------------------- #
def _taper(f: np.ndarray, f_hp: float | None, f_lp: float | None) -> np.ndarray:
    """Band-pass gain with raised-cosine edges: 0 below f_hp/2, 1 above f_hp;
    1 below f_lp, 0 above 1.25 f_lp."""
    g = np.ones_like(f)
    if f_hp:
        lo = f_hp / 2.0
        g[f <= lo] = 0.0
        band = (f > lo) & (f < f_hp)
        g[band] *= 0.5 - 0.5 * np.cos(np.pi * (f[band] - lo) / (f_hp - lo))
    if f_lp:
        hi = 1.25 * f_lp
        g[f >= hi] = 0.0
        band = (f > f_lp) & (f < hi)
        g[band] *= 0.5 + 0.5 * np.cos(np.pi * (f[band] - f_lp) / (hi - f_lp))
    return g


def spectral_integrate(
    x: np.ndarray,
    fs: float,
    order: int = 2,
    f_hp: float | None = 1.0,
    f_lp: float | None = None,
) -> np.ndarray:
    """Integrate ``order`` times in the frequency domain (negative ``order``
    differentiates), with a tapered band-pass [f_hp, f_lp].

    The signal is mirrored (even extension) before the FFT, which makes it
    periodic and continuous and removes the end-point leakage of a plain FFT.
    """
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 4:
        return np.zeros_like(x)
    ext = np.concatenate([x - x.mean(), (x - x.mean())[::-1]])
    spec = sfft.rfft(ext)
    f = sfft.rfftfreq(ext.size, 1.0 / fs)
    h = np.zeros(f.size, dtype=complex)
    nz = f > 0
    h[nz] = (2j * np.pi * f[nz]) ** (-order)
    h *= _taper(f, f_hp, f_lp)
    return sfft.irfft(spec * h, ext.size)[:n]


def _mirror_filter(x: np.ndarray, fs: float, gain) -> np.ndarray:
    """Apply the frequency response ``gain(f)`` to the even extension of x."""
    n = x.size
    ext = np.concatenate([x, x[::-1]])
    f = sfft.rfftfreq(ext.size, 1.0 / fs)
    return sfft.irfft(sfft.rfft(ext) * gain(f), ext.size)[:n]


def frequency_integrate(
    x: np.ndarray,
    fs: float,
    order: int = 2,
    f_hp: float | None = 1.0,
    f_lp: float | None = None,
) -> np.ndarray:
    """Integrate ``order`` times in the frequency domain, removing the linear
    trend after each step, then band-pass [f_hp, f_lp] (tapered).

    Each 1/(j 2 pi f) step on the mirrored record returns the zero-mean
    periodic solution, which differs from the true integral by a linear
    term (the unknown integration constant). Filtering that ramp directly
    leaves errors of tens of percent in the last 1/f_hp seconds whenever the
    record ends mid-cycle; detrending first removes it (checked against the
    analytic integral of the synthetic data: amplitude within 0.1 % up to
    the record end).
    """
    def inv(f):
        h = np.zeros(f.size, dtype=complex)
        h[f > 0] = 1.0 / (2j * np.pi * f[f > 0])
        return h

    y = np.asarray(x, dtype=float)
    y = y - y.mean()
    for _ in range(order):
        y = ss.detrend(_mirror_filter(y, fs, inv), type="linear")
    if f_hp or f_lp:
        y = _mirror_filter(y, fs, lambda f: _taper(f, f_hp, f_lp))
    return y


def time_integrate(
    x: np.ndarray,
    fs: float,
    order: int = 2,
    f_hp: float = 1.0,
) -> np.ndarray:
    """High-pass + trapezoidal integration, repeated ``order`` times (all
    filters zero-phase)."""
    sos = ss.butter(2, f_hp, btype="highpass", fs=fs, output="sos")
    y = ss.sosfiltfilt(sos, np.asarray(x, dtype=float) - np.mean(x))
    for _ in range(order):
        y = cumulative_trapezoid(y, dx=1.0 / fs, initial=0.0)
        y = ss.sosfiltfilt(sos, y)
    return y


def acceleration_to_displacement(
    a: np.ndarray,
    fs: float,
    f_hp: float = 1.0,
    f_lp: float | None = None,
    method: str = "frequency",
) -> np.ndarray:
    """Displacement [m] from acceleration [m/s^2]."""
    if method == "time":
        d = time_integrate(a, fs, order=2, f_hp=f_hp)
        if f_lp:
            d = ss.sosfiltfilt(
                ss.butter(4, f_lp, btype="lowpass", fs=fs, output="sos"), d)
        return d
    return frequency_integrate(a, fs, order=2, f_hp=f_hp, f_lp=f_lp)


def displacement_to_acceleration(
    x: np.ndarray,
    fs: float,
    f_lp: float | None = None,
    f_hp: float | None = None,
) -> np.ndarray:
    """Second derivative in the frequency domain; a low-pass ``f_lp`` is
    strongly advised (differentiation amplifies high-frequency noise by
    (2 pi f)^2)."""
    return spectral_integrate(x, fs, order=-2, f_hp=f_hp, f_lp=f_lp)


def sine_amplitude_to_displacement(a_amp: float, f: float) -> float:
    """|X| = |A| / (2 pi f)^2 at a single frequency (planejamento 15)."""
    return a_amp / (2.0 * np.pi * f) ** 2
