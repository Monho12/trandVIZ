"""
Өгөгдөл цэвэрлэх.  Ажиллуулах:  python -m src.clean   ->  data/processed/clean.parquet

Алхмууд (notebooks/02_cleaning_eda.ipynb-д дэлгэрэнгүй тайлбартай):
1. Нэр солигдсон нийтлэлийн хуучин нэрийн уншилтыг шинэ нэрэнд нэмэх
2. Өдөр бүрээр дүүргэх: API 0 уншилттай өдрийг огт буцаадаггүй -> 0 гэж нөхнө
3. Нийтлэл "идэвхтэй" болохоос өмнөх өдрүүдийг хасах (redirect/ноорог байсан үе)
4. Нэг өдрийн тусгаарлагдсан огцом өсөлтийг (ихэвчлэн бот) илрүүлж, хязгаарлах
5. Анхаарлын хувь: сэдвийн уншилт / тухайн өдрийн Wikipedia-ийн нийт уншилт (сая тутамд), log1p
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"

ACTIVE_SHARE = 0.02    # сүүлийн 1 жилийн медианы 2%-иас дээш болсон өдрөөс "идэвхтэй" гэж үзнэ
ACTIVE_ABS = 100       # ... ЭСВЭЛ өдөрт 100+ уншилттай болсон өдрөөс (жинхэнэ бага сонирхлыг хасахгүйн тулд)
SPIKE_X = 10           # медианаас 10+ дахин их ...
NEIGHBOR_X = 2         # ... бөгөөд өмнөх, дараагийн өдөр нь медианы 2 дахинаас бага бол тусгаарлагдсан огцом өсөлт


def merge_aliases(pv: pd.DataFrame, alias: pd.DataFrame) -> pd.DataFrame:
    """Хуучин нэрийн уншилтыг шинэ нэрэнд нэмнэ (өдөр бүрээр нийлбэр)."""
    cat = pv.drop_duplicates("article").set_index("article")["category"]
    al = alias.assign(category=alias["article"].map(cat))[["date", "article", "category", "views"]]
    return (pd.concat([pv, al], ignore_index=True)
              .groupby(["article", "category", "date"], as_index=False)["views"].sum())


def fill_days(df: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    """Нийтлэл бүрийг эхний өдрөөс end хүртэл өдөр бүрээр дүүргэнэ. Дутуу өдөр = 0 уншилт."""
    out = []
    for (a, c), g in df.groupby(["article", "category"]):
        s = g.set_index("date")["views"].reindex(pd.date_range(g["date"].min(), end), fill_value=0)
        out.append(pd.DataFrame({"date": s.index, "article": a, "category": c, "views": s.values,
                                 "was_missing": ~s.index.isin(g["date"])}))
    return pd.concat(out, ignore_index=True)


def trim_inactive(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Нийтлэл жинхэнэ утгаараа "амьд" болохоос өмнөх өдрүүдийг хасна."""
    keep, report = [], []
    for a, g in df.groupby("article", sort=False):
        g = g.sort_values("date")
        level = g["views"].tail(365).median()
        roll = g["views"].rolling(7, min_periods=1).mean()
        ok = (roll >= ACTIVE_SHARE * max(level, 1)) | (roll >= ACTIVE_ABS)
        start = g.loc[ok.idxmax(), "date"] if ok.any() else g["date"].iloc[-1]
        cut = (g["date"] < start).sum()
        report.append({"article": a, "start": start, "removed_days": int(cut)})
        keep.append(g[g["date"] >= start])
    return pd.concat(keep, ignore_index=True), pd.DataFrame(report)


def cap_isolated_spikes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Нэг өдрийн тусгаарлагдсан огцом өсөлтийг илрүүлнэ.
    Жинхэнэ мэдээний шуугиан хэд хоног "сүүлтэй" байдаг; бот ихэвчлэн ганц өдөр гэнэт гарч алга болдог.
    Илэрсэн өдрийн утгыг хөршүүдийнх нь дээд утгаар сольж, is_spike=True гэж тэмдэглэнэ.
    """
    out = []
    for _, g in df.groupby("article", sort=False):
        g = g.sort_values("date").copy()
        v = g["views"].astype(float)
        med = v.rolling(29, center=True, min_periods=7).median().clip(lower=1)
        prev, nxt = v.shift(1), v.shift(-1)
        spike = (v > SPIKE_X * med) & (prev < NEIGHBOR_X * med) & (nxt < NEIGHBOR_X * med)
        g["is_spike"] = spike.fillna(False)
        g["views_raw"] = g["views"]
        g.loc[g["is_spike"], "views"] = np.maximum(prev, nxt)[g["is_spike"]].round().astype("int64")
        out.append(g)
    return pd.concat(out, ignore_index=True)


def add_attention(df: pd.DataFrame, total: pd.DataFrame) -> pd.DataFrame:
    """attention = сэдвийн уншилт / нийт уншилт * 1e6 (сая уншилт тутамд); y = log1p(attention)."""
    df = df.merge(total, on="date", how="left")
    df["attention"] = df["views"] / df["total_views"] * 1e6
    df["y"] = np.log1p(df["attention"])
    return df


def build() -> pd.DataFrame:
    pv = pd.read_parquet(P / "pageviews.parquet")
    alias = pd.read_parquet(P / "alias_pageviews.parquet")
    total = pd.read_parquet(P / "total_views.parquet")
    end = pv["date"].max()

    df = merge_aliases(pv, alias)
    df = fill_days(df, end)
    df, trim_report = trim_inactive(df)
    df = cap_isolated_spikes(df)
    df = add_attention(df, total)
    df = df.sort_values(["article", "date"]).reset_index(drop=True)
    cols = ["date", "article", "category", "views", "views_raw", "total_views", "attention", "y", "is_spike", "was_missing"]
    out = df[cols].copy()
    out["article"] = out["article"].astype("category")
    out["category"] = out["category"].astype("category")
    for c in ("attention", "y"):
        out[c] = out[c].astype("float32")
    out.to_parquet(P / "clean.parquet", index=False, compression="zstd")
    trim_report.to_csv(P / "trim_report.csv", index=False)
    return df[cols]


if __name__ == "__main__":
    d = build()
    print(f"clean.parquet: {len(d):,} мөр, {d['article'].nunique()} сэдэв, "
          f"тусгаарлагдсан өсөлт {int(d['is_spike'].sum())}, нөхсөн өдөр {int(d['was_missing'].sum())}")
