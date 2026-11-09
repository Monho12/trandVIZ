"""
Scoring: ADR 0001/0002/0003/0004/0005-ын дүрмүүд нэг газар.

Үнэлгээ (04_model) ба вэб (snapshot) хоёулаа ЭНЭ модулийг ашиглана. Ингэснээр pct, ↑, 🔥 гэх мэт
нэг тэмдэг хоёр газар өөр утгатай болохгүй. Бүх функц цэвэр (pure): файл уншихгүй, төлөв хадгалахгүй.

Хуваарь:  x = анхаарал (сая уншилт тутамд),  y = log1p(x),  Δ = y_h − y_0.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.features import TRAIN_END

# Үнэн trend (ADR 0001), зөвхөн үнэлгээнд
TREND_UP, TREND_DOWN = 0.25, -0.20
UP, DOWN, STABLE = "↑ өсөж байна", "↓ унаж байна", "тогтвортой"

# 🔥 ба сум (ADR 0004), таамагласан pct(h3) дээр
T_FLOOR = 0.25
FIRE, RISE, FLAT, DIP, FALL = "🔥", "↗", "≈", "↘", "↓"

# Хэмжигдэх сэдэв (ADR 0004): сүүлийн 7 хоногийн дундаж анхаарал (x хуваарьт) ≥ 1
MEASURABLE_MIN, MEASURABLE_DAYS = 1.0, 7
TOP_N = 10

# Сэдвийн бүлэг (ADR 0005), viral_articles.csv-ийн peak_month-аар
GROUP_CURATED, GROUP_OLD_VIRAL, GROUP_NEW_VIRAL = "а", "б", "в"
LAST_OLD_VIRAL_MONTH = TRAIN_END.to_period("M")   # train-ийн сүүлийн сар = 2025-06
BUSAD = "Бусад"

# Харуулах (ADR 0003)
ROUND_STEP, CAP_PCT, CAP_TEXT = 0.05, 3.0, "↑ 3×-ээс их"
_EPS = 1e-9   # expm1(log1p(x)) нь x-ээс ~1e-15-аар зөрж болно; хил дээрх сэдвийг унагахгүйн тулд


def pct(y_0, y_h):
    """Өөрчлөлтийн хувь x_h / x_0 − 1, лог хуваарийн y_0, y_h-аас (ADR 0003). Бодит pct-д ч үүнийг ашиглана."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.expm1(y_h) / np.expm1(y_0) - 1


def predicted_pct(y_0, delta):
    """Таамагласан pct: x̂_h = expm1(y_0 + Δ̂), pct = x̂_h / x_0 − 1. exp(Δ̂) − 1 БИШ.
    80% интервалын хил (10%/90%-ийн квантил Δ) мөн үүгээр хувиргагдана (ADR 0003: квантил хадгалагдана)."""
    return pct(y_0, np.add(y_0, delta))


def true_trend(actual_pct: pd.Series) -> pd.Series:
    """Үнэн trend (ADR 0001): БОДИТ pct(h3) ≥ +25% -> ↑, ≤ −20% -> ↓, бусад нь тогтвортой. NaN -> None."""
    a = pd.Series(actual_pct)
    out = pd.Series(np.where(a >= TREND_UP, UP, np.where(a <= TREND_DOWN, DOWN, STABLE)), index=a.index, dtype=object)
    return out.where(a.notna(), None)


def fire_threshold(tuned: float) -> float:
    """T = max(тааруулсан, 25%) (ADR 0004): valid дээр ямар ч утга гарсан 🔥 нь +25%-иас доош буухгүй."""
    return max(float(tuned), T_FLOOR)


def arrow(pred_pct: pd.Series, tuned_T: float, measurable: pd.Series) -> pd.Series:
    """Таамагласан pct(h3)-ийн сум (ADR 0004):
    ≥ T 🔥 (зөвхөн хэмжигдэх сэдэв);  +10% … T ↗;  ±10% ≈;  −20% … −10% ↘;  ≤ −20% ↓.
    Хэмжигдэхгүй сэдэв T-ээс давсан ч ↗ авна. T = fire_threshold(tuned_T) энд дотроо тооцогдоно."""
    T = fire_threshold(tuned_T)
    p = pd.Series(pred_pct)
    m = pd.Series(measurable, index=p.index).fillna(False).astype(bool)
    conds = [((p >= T) & m).to_numpy(), (p >= 0.10).to_numpy(), (p > -0.10).to_numpy(), (p > -0.20).to_numpy()]
    out = pd.Series(np.select(conds, [FIRE, RISE, FLAT, DIP], default=FALL), index=p.index, dtype=object)
    return out.where(p.notna(), None)


def is_measurable(df: pd.DataFrame) -> pd.Series:
    """df: [article, date, y] (өдөр бүрээр, сэдэв бүрт дараалсан). Мөр бүрт: t-6 … t өдрийн дундаж
    x = expm1(y) ≥ 1 юу (ADR 0004). `roll_mean_7` (log1p хуваарьт) биш. Түүх 7 өдрөөс дутуу бол False.
    Буцаах Series нь df-ийн index-тэй."""
    d = df.sort_values(["article", "date"])
    x = np.expm1(d["y"])
    mean7 = (x.groupby(d["article"], observed=True, sort=False)
             .rolling(MEASURABLE_DAYS, min_periods=MEASURABLE_DAYS).mean()
             .reset_index(level=0, drop=True))
    return (mean7 >= MEASURABLE_MIN - _EPS).reindex(df.index)


def top10(df: pd.DataFrame, pct_col: str, measurable_col: str = "measurable") -> pd.DataFrame:
    """Өдөр бүрийн top-10 (ADR 0004): зөвхөн хэмжигдэх сэдэв, `pct_col`-оор буурахаар (тэнцвэл article нэрээр).
    Загварт pct_col = таамагласан pct(h3), momentum baseline-д pct_m (ADR 0002). Үргэлж яг 10 сэдэв:
    аль нэг өдөр 10-аас цөөн хэмжигдэх сэдэв байвал ValueError. Буцаах: тэр мөрүүд + `rank` (1…10)."""
    m = df[df[measurable_col].fillna(False).astype(bool) & df[pct_col].notna()]
    per_day = m.groupby("date").size().reindex(pd.Index(df["date"].unique()), fill_value=0)
    bad = per_day[per_day < TOP_N]
    if len(bad):
        raise ValueError(f"top-10: {len(bad)} өдөрт хэмжигдэх сэдэв 10-аас цөөн, жишээ {bad.index[0]}: {bad.iloc[0]}")
    top = (m.sort_values(["date", pct_col, "article"], ascending=[True, False, True])
           .groupby("date", sort=False).head(TOP_N).copy())
    top["rank"] = top.groupby("date").cumcount() + 1
    return top.reset_index(drop=True)


def topic_group(peak_month: pd.Series) -> pd.Series:
    """Сэдвийн бүлэг (ADR 0005): peak_month хоосон (сонгосон сэдэв) -> а; ≤ 2025-06 -> б; ≥ 2025-07 -> в.
    peak_month нь "YYYY-MM" мөр. Сонгосон сэдэвт (articles.csv) NaN/None дамжуулна."""
    pm = pd.Series(peak_month)
    per = pd.PeriodIndex(pm.where(pm.notna(), None), freq="M")
    out = np.where(per.isna(), GROUP_CURATED,
                   np.where(per <= LAST_OLD_VIRAL_MONTH, GROUP_OLD_VIRAL, GROUP_NEW_VIRAL))
    return pd.Series(out, index=pm.index, dtype=object)


def display_category(category: pd.Series) -> pd.Series:
    """Вэбэд харуулах ангилал (ADR 0005): "viral" -> "Бусад", бусад нь хэвээр."""
    c = pd.Series(category).astype(object)
    return c.where(c != "viral", BUSAD)


def momentum_direction(y_0, y_m3):
    """Momentum baseline-ийн чиглэл (ADR 0002): sign(y_0 − y_{−3}) = sign(growth_3). +1 / 0 / −1."""
    return np.sign(np.subtract(y_0, y_m3))


def momentum_pct(y_0, y_m3):
    """Momentum baseline-ийн top-10-ийн эрэмбэ (ADR 0002): pct_m = x_0 / x_{−3} − 1 (загварын pct-тэй ижил хуваарь)."""
    return pct(y_m3, y_0)


def round_pct(p: float) -> float:
    """5%-д дугуйлна, хагас нь тэгээс холдоно (+12.5% -> +15%, −12.5% -> −15%)."""
    steps = np.floor(abs(p) / ROUND_STEP + 0.5 + _EPS)
    return float(np.copysign(steps * ROUND_STEP, p)) if steps else 0.0


def format_pct(p: float) -> str:
    """Вэбийн тоо (ADR 0003): "+75%", "−20%", "0%"; +300%-иас их бол "↑ 3×-ээс их". NaN -> ""."""
    if p is None or np.isnan(p):
        return ""
    if p > CAP_PCT:
        return CAP_TEXT
    r = round(round_pct(p) * 100)
    return "0%" if r == 0 else f"+{r}%" if r > 0 else f"−{-r}%"
