"""
Feature engineering — суурь хувилбар (Даваа гарагт 03 notebook-оор өргөтгөнө).

Санаа: "таамаг гаргах өдөр" t-д бид t өдрийг ОРОЛЦУУЛАН өмнөх бүх зүйлийг мэднэ.
Ирээдүйн (t+1, t+2, t+3) утгыг ХЭЗЭЭ Ч feature-т оруулахгүй -> data leakage-гүй.

  y_0       = t өдрийн log(анхаарал)   (сүүлд мэдэгдэж буй утга)
  lag_k     = t-k өдрийн утга          (k өдрийн өмнө)
  roll_*_w  = t-w+1 ... t хүртэлх w өдрийн дундаж / хэлбэлзэл / дээд утга
  y_h1..h3  = t+1, t+2, t+3 өдрийн утга (TARGET, feature биш)

Бүх тооцоог нийтлэл тус бүрээр (groupby) хийнэ -> нэг сэдвийн утга нөгөө рүү "нэвчихгүй".

Ажиллуулах:  python -m src.features  ->  data/processed/features.parquet
(feature_list.json-ийн 18 feature-ийг ашиглана; жагсаалтыг 03 notebook сонгодог)
"""
from __future__ import annotations

import json
from pathlib import Path

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

    # Оргилоос хойш хэдэн хоног өнгөрсөн бэ (сүүлийн 28 хоногт). Вирал сэдэв унтрахыг таамаглахад тусална
    pos = g.rolling(28, min_periods=28).apply(lambda x: len(x) - 1 - int(np.argmax(x)), raw=True)
    d["days_since_peak"] = pos.reset_index(level=0, drop=True)

    # Сэдвийн урт хугацааны "ердийн" түвшин: сүүлийн 365 хоногийн медиан (зөвхөн өнгөрсөн)
    d["level_365"] = g.rolling(365, min_periods=28).median().reset_index(level=0, drop=True)
    d["vs_level"] = d["y_0"] - d["level_365"]           # өнөөдөр ердийн түвшнээсээ хэр дээр вэ

    # Ангилал: LightGBM categorical feature (нийтлэлийн НЭР биш)
    d["category"] = d["category"].astype("category")

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
                 + ["growth_1", "growth_3", "ratio_7", "from_max_28", "days_since_peak", "level_365", "vs_level",
                    "category", "dow", "is_weekend", "month", "doy_sin", "doy_cos"])

# Feature-үүдийн бүлэг (ablation шалгалтад)
GROUPS = {
    "lag": [f"lag_{k}" for k in LAGS],
    "rolling": [f"roll_{s}_{w}" for w in WINDOWS for s in ("mean", "std")] + ["roll_max_28"],
    "өсөлт": ["growth_1", "growth_3", "ratio_7", "from_max_28"],
    "оргил": ["days_since_peak"],
    "түвшин": ["level_365", "vs_level"],
    "ангилал": ["category"],
    "календарь": ["dow", "is_weekend", "month", "doy_sin", "doy_cos"],
}

# Цаг хугацааны хуваалт (санамсаргүй холихгүй!)
TRAIN_END, VALID_END = pd.Timestamp("2025-06-30"), pd.Timestamp("2026-03-31")


def split_of(dates: pd.Series) -> pd.Series:
    return pd.Series(np.where(dates <= TRAIN_END, "train", np.where(dates <= VALID_END, "valid", "test")), index=dates.index)


def purge_split_boundary(f: pd.DataFrame) -> pd.DataFrame:
    """Хуваалтын хил дээрх purge: t+h (h = 1..max(HORIZONS)) нь мөрийнхөө хуваалтаас гарч байвал тэр мөрийг хасна.
    Жишээ: 2025-06-29-ний train мөрийн y_h2 = 2025-07-01 (valid) -> train руу valid-ийн мэдээлэл нэвчинэ.
    Ингэснээр train/valid ба valid/test хил бүр дээр max(HORIZONS) = 3 өдөр хасагдана."""
    last = f["date"] + pd.Timedelta(days=max(HORIZONS))
    return f[split_of(last).to_numpy() == f["split"].to_numpy()]


P = Path(__file__).resolve().parents[1] / "data" / "processed"


def build() -> pd.DataFrame:
    """clean.parquet -> features.parquet. Түүх хүрэлцэхгүй (эхний 28+ өдөр) ба target-гүй мөрийг хасна."""
    cl = pd.read_parquet(P / "clean.parquet", columns=["date", "article", "category", "y"])
    final = json.loads((P / "feature_list.json").read_text(encoding="utf-8"))["features"]
    f = make_features(cl)
    f["split"] = split_of(f["date"])
    num = [c for c in FEATURES_BASE if c != "category"]
    f = f.dropna(subset=num + [f"y_h{h}" for h in HORIZONS])
    f = purge_split_boundary(f)
    out = f[["date", "article", "split", "y_0"] + [f"y_h{h}" for h in HORIZONS] + final]
    out.to_parquet(P / "features.parquet", index=False, compression="zstd")
    return out


if __name__ == "__main__":
    d = build()
    n_feat = len(json.loads((P / "feature_list.json").read_text(encoding="utf-8"))["features"])
    print(f"features.parquet: {len(d):,} мөр, {n_feat} feature;", d["split"].value_counts().to_dict())
