"""
Мөчлөг ба илүүдэл (ADR 0019): нүүрний жагсаалт "ердийнхөөсөө давж өснө" гэсэн асуултад хариулна.

  Мөчлөг (h3) = сүүлийн 4 долоо хоногийн ижил гарагийн шилжилтийн (t−7k → t−7k+3, k = 1…4) анхаарлын харьцааны медиан − 1
  Илүүдэл e  = (1 + pct) / (1 + мөчлөг) − 1        (таамагласан pct бол илүүдэл, бодит pct бол бодит илүүдэл)

t өдрийн мөчлөг нь t−28 … t−4 өдрийн анхаарлаас л гарна: t-ээс хойших өгөгдлөөс хамаарахгүй.
Үнэлгээ ба вэб (src/serve.py) хоёулаа ЭНЭ модулийг ашиглана. Бүх функц цэвэр (pure).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.scoring import DECLINING, RISING, TOP_N

WEEKS, H = 4, 3                      # сүүлийн 4 долоо хоног, asof гараг → asof+3 гараг
HISTORY_DAYS = 7 * WEEKS             # asof-оос өмнө хэрэгтэй түүх (t−28 … t−4)
# Rising / Declining (таамагласан pct ≥ +10% / ≤ −10%) нь src/scoring.py-д (сумтай нэг хил)
CYCLE_MIN, EXCESS_BAND = 0.10, 0.10  # мөчлөг ≥ +10% (≤ −10%) ба илүүдэл < +10% (> −10%)


def cycle(df: pd.DataFrame) -> pd.Series:
    """df: [article, date, attention] (сэдэв бүрт өдөр тутмын, дутуугүй: clean.COLS). Буцаах: df-ийн index-тэй мөчлөг.
    4 шилжилтийн аль нэг нь байхгүй (түүх < 28 хоног) эсвэл тодорхойгүй (эхлэх өдөр 0 анхаарал) бол NaN."""
    d = df.sort_values(["article", "date"])
    g = d["attention"].astype(float).groupby(d["article"], observed=True, sort=False)
    ratios = []
    for k in range(1, WEEKS + 1):
        start, end = g.shift(7 * k).to_numpy(), g.shift(7 * k - H).to_numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            ratios.append(np.where(start > 0, end / start, np.nan))
    med = np.median(np.column_stack(ratios), axis=1) - 1      # NaN нь NaN хэвээр (skipna биш)
    return pd.Series(med, index=d.index).reindex(df.index)


def excess(pct, cyc):
    """Илүүдэл = (1 + pct) / (1 + мөчлөг) − 1. Мөчлөг тодорхойгүй эсвэл −100% бол NaN."""
    with np.errstate(divide="ignore", invalid="ignore"):
        e = np.divide(np.add(1, pct), np.add(1, cyc)) - 1
    return np.where(np.isfinite(e), e, np.nan)


def is_cyclical_rise(pct, cyc):
    """Мөчлөгийн өсөлт ⇔ Rising, мөчлөг ≥ +10% ба илүүдэл < +10%. Нэг талын: мөчлөгөөсөө БАГА өсөх Rising
    (мөчлөг +30%, таамаг +15%) мөн мөчлөгийн өсөлт, жирийн Rising болж жагсаалтад орохгүй. NaN -> False."""
    e = excess(pct, cyc)
    with np.errstate(invalid="ignore"):
        return (np.asarray(pct) >= RISING) & (np.asarray(cyc) >= CYCLE_MIN) & (e < EXCESS_BAND)


def is_cyclical_fall(pct, cyc):
    """Мөчлөгийн бууралт ⇔ Declining, мөчлөг ≤ −10% ба илүүдэл > −10%. NaN -> False."""
    e = excess(pct, cyc)
    with np.errstate(invalid="ignore"):
        return (np.asarray(pct) <= DECLINING) & (np.asarray(cyc) <= -CYCLE_MIN) & (e > -EXCESS_BAND)


def _ranked(df: pd.DataFrame, keep, pct_col: str, n: int | None) -> pd.DataFrame:
    """keep мөрүүдийг өдөр бүрт pct_col-оор буурахаар (тэнцвэл article нэрээр), эхний n (None бол бүгд) + `rank`."""
    r = df[np.asarray(keep, dtype=bool)].sort_values(["date", pct_col, "article"], ascending=[True, False, True])
    if n is not None:
        r = r.groupby("date", sort=False).head(n)
    r = r.copy()
    r["rank"] = r.groupby("date").cumcount() + 1
    return r.reset_index(drop=True)


def _measurable_pct_cycle(df: pd.DataFrame, pct_col: str, cycle_col: str, measurable_col: str):
    meas = df[measurable_col].fillna(False).astype(bool).to_numpy()
    return meas, df[pct_col].to_numpy(float), df[cycle_col].to_numpy(float)


def beyond_list(df: pd.DataFrame, pct_col: str = "pred_pct", cycle_col: str = "cycle",
                measurable_col: str = "measurable") -> pd.DataFrame:
    """Давж өсөх жагсаалт (ADR 0019), өдөр бүрт: хэмжигдэх сэдвийн мөчлөгийн өсөлт биш Rising, таамагласан pct (h3)-ээр,
    дээд тал нь 10, цөөн бол цөөн (Stable-аар нөхөхгүй). ADR 0004-ийн "top-10 үргэлж 10"-г нүүрэнд орлоно
    (precision@10-ийн тодорхойлолт `scoring.top10` хэвээр). Буцаах: тэр мөрүүд + `rank` (1…≤10)."""
    meas, p, c = _measurable_pct_cycle(df, pct_col, cycle_col, measurable_col)
    return _ranked(df, meas & (p >= RISING) & ~is_cyclical_rise(p, c), pct_col, TOP_N)


def cyclical_rise_list(df: pd.DataFrame, pct_col: str = "pred_pct", cycle_col: str = "cycle",
                       measurable_col: str = "measurable") -> pd.DataFrame:
    """Мөчлөгийн өсөлтийн тусдаа жагсаалт, өдөр бүрт: хэмжигдэх сэдвийн мөчлөгийн өсөлт, таамагласан pct (h3)-ээр, бүгд."""
    meas, p, c = _measurable_pct_cycle(df, pct_col, cycle_col, measurable_col)
    return _ranked(df, meas & is_cyclical_rise(p, c), pct_col, None)
