"""
Feature engineering — суурь хувилбар (Даваа гарагт 03 notebook-оор өргөтгөнө).

Санаа: "таамаг гаргах өдөр" t-д бид t өдрийг ОРОЛЦУУЛАН өмнөх бүх зүйлийг мэднэ.
Ирээдүйн (t+1, t+2, t+3) утгыг ХЭЗЭЭ Ч feature-т оруулахгүй -> data leakage-гүй.

  y_0       = t өдрийн log(анхаарал)   (сүүлд мэдэгдэж буй утга)
  lag_k     = t-k өдрийн утга          (k өдрийн өмнө)
  roll_*_w  = t-w+1 ... t хүртэлх w өдрийн дундаж / хэлбэлзэл / дээд утга
  y_h1..h3  = t+1, t+2, t+3 өдрийн утга (TARGET, feature биш)

Бүх тооцоог нийтлэл тус бүрээр (groupby) хийнэ -> нэг сэдвийн утга нөгөө рүү "нэвчихгүй".
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = [1, 2, 3, 7, 14]
WINDOWS = [3, 7, 14, 28]
HORIZONS = [1, 2, 3]


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """df: [date, article, category, y] (өдөр бүрээр, дутуугүй). Буцаах: feature + target хүснэгт."""
    d = df.sort_values(["article", "date"]).reset_index(drop=True).copy()
    g = d.groupby("article", observed=True, sort=False)["y"]

    d["y_0"] = d["y"]
    for k in LAGS:
        d[f"lag_{k}"] = g.shift(k)

    for w in WINDOWS:
        r = g.rolling(w, min_periods=w)
        d[f"roll_mean_{w}"] = r.mean().reset_index(level=0, drop=True)
        d[f"roll_std_{w}"] = r.std().reset_index(level=0, drop=True)
    d["roll_max_28"] = g.rolling(28, min_periods=28).max().reset_index(level=0, drop=True)

    # Өсөлт ба харьцаа (log хуваарьт хасах = харьцаа)
    d["growth_1"] = d["y_0"] - d["lag_1"]
    d["growth_3"] = d["y_0"] - d["lag_3"]
    d["ratio_7"] = d["y_0"] - d["roll_mean_7"]          # өнөөдөр 7 хоногийн дунджаас хэр их вэ
    d["from_max_28"] = d["y_0"] - d["roll_max_28"]      # 28 хоногийн оргилоосоо хэр доор вэ

    # Календарь (t өдрийнх; horizon бүрт тусдаа model тул зорилтот өдрийн гараг үүнээс тодорхой)
    d["dow"] = d["date"].dt.dayofweek
    d["is_weekend"] = (d["dow"] >= 5).astype("int8")
    d["month"] = d["date"].dt.month
    doy = d["date"].dt.dayofyear
    d["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    d["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)

    # Target: ирээдүйн утгууд (зөвхөн сургалт/үнэлгээнд)
    for h in HORIZONS:
        d[f"y_h{h}"] = g.shift(-h)
    return d


FEATURES_BASE = (["y_0"] + [f"lag_{k}" for k in LAGS]
                 + [f"roll_{s}_{w}" for w in WINDOWS for s in ("mean", "std")] + ["roll_max_28"]
                 + ["growth_1", "growth_3", "ratio_7", "from_max_28",
                    "dow", "is_weekend", "month", "doy_sin", "doy_cos"])
