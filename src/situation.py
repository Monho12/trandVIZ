"""
Нөхцөл байдлын код ба track record (ADR 0020), Anomaly-ийн "үргэлжлэх / унтрах" дүгнэлт (ADR 0021), #51.

Код нь ажиглагдах өгөгдлөөс (asof өдөр ба түүнээс өмнөх) гарсан нөхцөлийг дүрсэлнэ, model-ийн дотоод шалтгааныг БИШ.
Вэб (src/serve.py), сэргээж тооцсон backtest (src/backtest.py), хадгалсан таамгийн log (src/forecast_log.py) ба
track record (src/track_record.py) бүгд ЭНЭ модулийг ашиглана. Бүх функц цэвэр (pure).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.anomaly import Z_ANOMALY
from src.cycle import EXCESS_BAND, excess
from src.scoring import DECLINING, GROUP_NEW_VIRAL, RISING, T_FLOOR
from src.train import short_version

# ---------------------------------------------------------------- дүгнэлт (ADR 0021, "Тодорхойлолт")
# Anomaly сэдвийн таамагласан pct (h3) ≤ −10% -> унтрах, бусад -> үргэлжлэх. Сайтын сумтай нэг хил (src/scoring.py).
FADE_MAX = DECLINING
VERDICTS = {"continue": "үргэлжлэх", "fade": "унтрах"}


def verdict(pct_h3, anomaly) -> np.ndarray:
    """Мөр бүрт "continue" / "fade", Anomaly биш эсвэл таамаг тодорхойгүй (NaN) бол None."""
    p = np.asarray(pct_h3, dtype=float)
    a = np.asarray(anomaly, dtype=bool)
    with np.errstate(invalid="ignore"):
        out = np.where(p <= FADE_MAX, "fade", "continue").astype(object)
    out[~a | ~np.isfinite(p)] = None
    return out


# ---------------------------------------------------------------- нөхцөл байдлын код (ADR 0020)
# Дарааллаар нь (эхэнд таарсан нь): ADR 0020-ийн тархалт (valid, жирийн Rising өдөрт 14.1: Буцалт 95%, тодорхой бус 4%,
# Үргэлжилж буй өсөлт 1%) энэ дарааллаар гарна. y = log1p(анхаарал), бүгд asof өдөр ба түүнээс өмнөх өгөгдлөөс.
#   total       asof өдөр Wikipedia-ийн нийт уншилт ердийнхөөсөө огцом зөрсөн (anomaly.total_note, |z| ≥ 4): бүх сэдэвт
#   cycle       таамаг мөчлөгийн өсөлт эсвэл бууралт (ADR 0019)
#   rebound     Anomaly биш (z < 3), анхаарал 7 хоногийн (t−6 … t, лог) дунджаас ≥ 5% доор (features.ratio_7)
#   after_peak  сүүлийн 7 хоногт (t−7 … t−1) Anomaly өдөр (z ≥ 3) байсан, өнөөдрийн анхаарал тэр 7 хоногийн оргилоос доор
#   growing     анхаарал 7 хоногийн дунджаас ≥ 5% дээр ба 3 өдрийн өмнөхөөсөө өндөр (features.growth_3 > 0)
#   unclear     бусад
CODES = {"total": "Нийт уншилтын нөлөө", "cycle": "Мөчлөг", "rebound": "Буцалт",
         "after_peak": "Оргилын дараах бууралт", "growing": "Үргэлжилж буй өсөлт", "unclear": "Тодорхой бус"}
MEAN_BAND = 0.05        # 7 хоногийн дунджаас ±5%
PEAK_DAYS = 7           # "сүүлийн 7 хоног" = t−7 … t−1


def recent_peak(df: pd.DataFrame) -> pd.DataFrame:
    """df: [article, date, y, z] (сэдэв бүрт өдөр тутмын, дутуугүй). Буцаах: df-ийн index-тэй [peak_z, peak_y] =
    t−7 … t−1 өдрүүдийн хамгийн их z ба y (t өдөр өөрөө орохгүй). Түүх байхгүй бол NaN. t-ээс хойших өгөгдлөөс хамаарахгүй."""
    d = df.sort_values(["article", "date"])
    g = d.groupby("article", observed=True, sort=False)
    out = pd.DataFrame(index=d.index)
    for src, dst in (("z", "peak_z"), ("y", "peak_y")):
        out[dst] = g[src].transform(lambda s: s.shift(1).rolling(PEAK_DAYS, min_periods=1).max())
    return out.reindex(df.index)


def code(df) -> np.ndarray:
    """df: [ratio_7, growth_3, z, peak_z, peak_y, y_0, cyclical, total_day] (src/serve.feature_rows + predict). Буцаах: CODES-ийн түлхүүр.
    NaN нөхцөлийг хангахгүй (харьцуулалт False) тул тодорхойгүй оролт "unclear" руу орно."""
    col = lambda c: np.asarray(df[c], dtype=float)   # noqa: E731
    r7, g3, z, pz, py, y0 = (col(c) for c in ("ratio_7", "growth_3", "z", "peak_z", "peak_y", "y_0"))
    with np.errstate(invalid="ignore"):
        conds = [np.asarray(df["total_day"], dtype=bool), np.asarray(df["cyclical"], dtype=bool),
                 (r7 <= np.log1p(-MEAN_BAND)) & ~(z >= Z_ANOMALY),
                 (pz >= Z_ANOMALY) & (y0 < py),
                 (r7 >= np.log1p(MEAN_BAND)) & (g3 > 0)]
    return np.select(conds, ["total", "cycle", "rebound", "after_peak", "growing"], "unclear").astype(object)


# ---------------------------------------------------------------- таамгийн зурвас (таамагласан pct h3), сайтын сумтай нэг хил

BANDS = {"le_-20": "≤ −20%", "-20_-10": "−20…−10%", "pm10": "±10%", "10_25": "+10…+25%", "ge_25": "≥ +25%"}
# ↓ ≤ −20% < ↘ ≤ −10% < ≈ < +10% ≤ ↗ < +25% ≤. Дээд хил нь T-ийн доод хязгаар (T_FLOOR) тогтмол: тааруулсан T өөрчлөгдсөн ч
# зурвас өөрчлөгдөхгүй (issue #51-ийн зурвас), харин 🔥/хүчтэй ↗ нь T ≥ 25%-аар (src/scoring.arrow).
BAND_EDGES = (-0.20, DECLINING, RISING, T_FLOOR)


def band(pct_h3) -> np.ndarray:
    p = np.asarray(pct_h3, dtype=float)
    lo2, lo1, hi1, hi2 = BAND_EDGES
    with np.errstate(invalid="ignore"):
        conds = [p <= lo2, p <= lo1, p < hi1, p < hi2, p >= hi2]
    out = np.select(conds, list(BANDS), "").astype(object)
    out[~np.isfinite(p)] = None
    return out


# ---------------------------------------------------------------- track record (ADR 0020, 0021)
# Мөр: таамаг (asof D) + бодит үр дүн (h3 өдөр, ADR 0021). Хүрээ: хэмжигдэх сэдэв, (в)-гүй (ADR 0005), бодит үр дүн мэдэгдсэн.
# Эх сурвалж бүр (сэргээж тооцсон / хадгалсан) ба model хувилбар бүр тусдаа хүснэгт: хэзээ ч нэг тоо болгож холихгүй.

SOURCES = {"recomputed": "сэргээж тооцсон", "stored": "хадгалсан"}   # GLOSSARY: Сэргээж тооцсон / Хадгалсан таамаг
MIN_N = 20
INSUFFICIENT = "хангалтгүй"
ACTUAL_UP, ACTUAL_DOWN = RISING, DECLINING   # бодит ≥ +10% / ≤ −10% (≤ −10% = унтарсан, ADR 0021)
# Дүгнэлт бүрийн "биелсэн" үр дүн (hit ба ердийн үеийн base_hit хоёулаа үүгээр)
HELD = {"continue": lambda a: a > ACTUAL_DOWN, "fade": lambda a: a <= ACTUAL_DOWN}
POPULATION = "хэмжигдэх сэдэв, (в) бүлгийг хассан, бодит үр дүн (h3) мэдэгдсэн таамгууд"
COLS = ["asof", "measurable", "group", "model_hash", "pct_h3", "actual_pct_h3", "cycle", "situation", "anomaly", "verdict"]


def _share(mask: np.ndarray) -> float:
    return round(float(np.mean(mask)), 4)


def outcome(d: pd.DataFrame) -> dict:
    """n ба бодит ≥ +10%, > 0, ≤ −10%, бодит илүүдэл ≥ +10%-ийн хувь. n < MIN_N бол тоо биш "хангалтгүй".
    Илүүдэл нь мөчлөг мэдэгдсэн мөрүүд дээр: тэдгээр нь MIN_N-ээс цөөн бол excess10 = None."""
    n = len(d)
    if n < MIN_N:
        return {"n": n, "enough": False, "text": INSUFFICIENT, "up10": None, "up": None, "down10": None, "excess10": None}
    a = d["actual_pct_h3"].to_numpy(float)
    e = excess(a, d["cycle"].to_numpy(float))
    defined = np.isfinite(e)
    return {"n": n, "enough": True, "up10": _share(a >= ACTUAL_UP), "up": _share(a > 0), "down10": _share(a <= ACTUAL_DOWN),
            "excess10": _share(e[defined] >= EXCESS_BAND) if defined.sum() >= MIN_N else None}


def _by(d: pd.DataFrame, col: str, labels: dict) -> list[dict]:
    return [{"key": k, "label": v, **outcome(d[d[col] == k])} for k, v in labels.items()]


def track_record(rows: pd.DataFrame, source: str) -> dict:
    """rows: COLS (мөр бүр нэг таамаг). Хүрээг (POPULATION) энд шүүнэ. Нэг model хувилбартай байх ёстой (үгүй бол ValueError)."""
    versions = set(rows["model_hash"].astype(str))
    if len(versions) != 1:
        raise ValueError(f"track record нэг model хувилбартай байх ёстой, ирсэн нь {sorted(short_version(v) for v in versions)}")
    (h,) = versions
    keep = (rows["measurable"].fillna(False).astype(bool) & (rows["group"] != GROUP_NEW_VIRAL)
            & np.isfinite(rows["actual_pct_h3"].to_numpy(float)))
    d = rows[keep.to_numpy()].assign(band=lambda x: band(x["pct_h3"]))
    an = d[d["anomaly"].fillna(False).astype(bool)]
    held = lambda k, g: _share(HELD[k](g["actual_pct_h3"].to_numpy(float))) if len(g) >= MIN_N else None   # noqa: E731
    verdicts = []
    for k, v in VERDICTS.items():
        g = an[an["verdict"] == k]
        verdicts.append({"key": k, "label": v, **outcome(g), "hit": held(k, g), "base_hit": held(k, an)})
    dates = pd.to_datetime(d["asof"]) if len(d) else pd.to_datetime(rows["asof"])
    return {"source_key": source, "source": SOURCES[source], "model_hash": h, "model_version": short_version(h),
            "from": dates.min().strftime("%Y-%m-%d"), "through": dates.max().strftime("%Y-%m-%d"),
            "days": int(dates.nunique()), "population": POPULATION, "min_n": MIN_N,
            "base": outcome(d), "anomaly_base": outcome(an),
            "by_verdict": verdicts, "by_code": _by(d, "situation", CODES), "by_band": _by(d, "band", BANDS)}
