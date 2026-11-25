"""
Anomaly (ADR 0017): сэдвийн сүүлийн уншилт өөрийн ердийн түвшнээсээ огцом зөрсөн эсэх. Өнгөрсөн, таамаг биш.

  z = (y_t − медиан) / (1.4826 · max(MAD, 0.05)),  y = log1p(анхаарал)
  цонх = t−59 … t−7 (сүүлийн 7 хоногийг оруулахгүй), ≥ 28 цэг. Anomaly ⇔ z ≥ 3.

t өдрийн бүх тоо зөвхөн t өдрийн утга ба t−59 … t−7 цонхноос гарна: t-ээс хойших өгөгдлөөс хамаарахгүй.
Үнэлгээ ба вэб (src/serve.py) хоёулаа ЭНЭ модулийг ашиглана. Бүх функц цэвэр (pure).
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

WINDOW_FROM, WINDOW_TO = 59, 7        # t−59 … t−7
MIN_POINTS = 28
MAD_K, MAD_FLOOR = 1.4826, 0.05
Z_ANOMALY = 3.0
RECENT_FROM = 59                      # "сүүлийн 2 сард ийм өдөр хэдэн удаа": t−59 … t−1 (сүүлийн 7 хоног ОРНО)
# Нийт уншилт (ADR 0017, "Хуваагчийн эрсдэл"): z = log(нийт) дээр, ижил цонх, MAD floor-гүй
# (нийт уншилт өдөрт ±3%-иар л хэлбэлздэг тул 0.05 floor бол 2024-11-06-ний +13%-ийг ч барихгүй). |z| ≥ 4 бол өдрийн мөр.
Z_TOTAL = 4.0


def _windows(a: np.ndarray, start: int = WINDOW_FROM, end: int = WINDOW_TO) -> np.ndarray:
    """a: нэг сэдвийн өдөр тутмын цуваа. Мөр i = a-ийн i−start … i−end (эхэнд нь NaN)."""
    pad = np.concatenate([np.full(start, np.nan), a.astype(float)])
    return sliding_window_view(pad, start - end + 1)[:len(a)]


def _nanmedian(w: np.ndarray) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # хоосон цонх -> NaN
        return np.nanmedian(w, axis=1)


def _ratio(a: np.ndarray, base: np.ndarray) -> np.ndarray:
    """a / base, base ≤ 0 эсвэл NaN бол NaN (ердийн өдөр 0 уншилттай сэдэвт ×N тодорхойгүй)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(base > 0, a / base, np.nan)


def score(df: pd.DataFrame) -> pd.DataFrame:
    """df: [article, date, y, attention, views] (сэдэв бүрт өдөр тутмын, дутуугүй: clean.COLS).
    Буцаах: df-ийн index-тэй хүснэгт, мөр бүрт:
      z, anomaly    robust z ба z ≥ 3 (цонхонд < 28 цэг бол z = NaN, anomaly = False)
      ratio         ▲ ×N = анхаарал ÷ цонхны медиан анхаарал (сайтын бүх ×N, treemap-ийн өнгө)
      views_ratio   уншилт ÷ цонхны медиан уншилт (хаалтанд харуулах түүхий харьцаа)
      normal        "ердийн өдөр" = цонхны медиан уншилт
      typical_pct   сэдвийн ердийн хэлбэлзэл ±: expm1(1.4826 · max(MAD, 0.05))
      similar_days  "сүүлийн 2 сард ийм өдөр хэдэн удаа": t−59 … t−1-ийн y ≥ y_t өдрийн тоо. z-ийн цонхноос ялгаатай нь
                    сүүлийн 7 хоног орно: 3 өдрийн өмнө эхэлсэн өсөлтийг "нэг ч удаа гараагүй" гэвэл худал."""
    d = df.sort_values(["article", "date"])
    parts = []
    for _, g in d.groupby("article", observed=True, sort=False):
        y, x, v = (g[c].to_numpy(float) for c in ("y", "attention", "views"))
        w = _windows(y)
        n = np.count_nonzero(~np.isnan(w), axis=1)
        med = _nanmedian(w)
        sigma = MAD_K * np.maximum(_nanmedian(np.abs(w - med[:, None])), MAD_FLOOR)
        z = np.where(n >= MIN_POINTS, (y - med) / sigma, np.nan)
        normal = _nanmedian(_windows(v))
        parts.append(pd.DataFrame({
            "z": z, "anomaly": z >= Z_ANOMALY,
            "ratio": _ratio(x, _nanmedian(_windows(x))), "views_ratio": _ratio(v, normal), "normal": normal,
            "typical_pct": np.expm1(sigma), "similar_days": np.count_nonzero(_windows(y, RECENT_FROM, 1) >= y[:, None], axis=1),
        }, index=g.index))
    return pd.concat(parts).reindex(df.index)



def total_note(total: pd.DataFrame, asof: pd.Timestamp) -> dict | None:
    """total: [date, total_views]. asof өдрийн нийт уншилт ердийнхөөс (цонхны медиан) огцом зөрсөн бол
    {"z", "pct", "text"}, үгүй бол None. Anomaly-г нуухгүй: зөвхөн тайлбар нэмнэ."""
    t = total.set_index("date")["total_views"].astype(float)
    asof = pd.Timestamp(asof)
    win = t[(t.index >= asof - pd.Timedelta(days=WINDOW_FROM)) & (t.index <= asof - pd.Timedelta(days=WINDOW_TO))]
    if asof not in t.index or len(win) < MIN_POINTS:
        return None
    lw = np.log(win.to_numpy())
    med = np.median(lw)
    sigma = MAD_K * np.median(np.abs(lw - med))
    if not sigma > 0:
        return None
    z = (np.log(t[asof]) - med) / sigma
    if abs(z) < Z_TOTAL:
        return None
    pct = t[asof] / np.median(win.to_numpy()) - 1
    word = "их" if pct > 0 else "бага"
    return {"z": round(float(z), 1), "pct": float(pct),
            "text": f"Энэ өдөр Wikipedia-ийн нийт уншилт ердийнхөөс {round(abs(pct) * 100)}% {word} байсан."}
