"""
Өгөгдөл татах скрипт.  Ажиллуулах:  python -m src.fetch_data

Юу хийдэг вэ:
1. Англи Wikipedia-ийн нийт өдөр тутмын хандалтыг татна (анхаарлын хувийн "хуваарь").
2. data/articles.csv доторх ~150 сонгосон сэдвийн түүхийг татна.
3. 2021 оноос хойшхи сар бүрийн топ-1000 жагсаалтаас "богино хугацаанд
   гэнэт гарч ирээд алга болсон" ~150 вирал сэдвийг сонгож, түүхийг нь татна.
4. Бүгдийг data/processed/*.parquet болгон хадгална.

Татсан хариу бүр data/raw/cache/ дотор хадгалагдах тул дахин ажиллуулахад хурдан.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src import wiki

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = DATA / "raw" / "cache"
OUT = DATA / "processed"

START = pd.Timestamp("2021-01-01")
N_VIRAL = 150          # хэдэн вирал сэдэв авах вэ
VIRAL_MIN_RATIO = 8    # оргил өдөр нь медианаасаа дор хаяж хэд дахин их байх вэ
SEED = 42


def latest_available_day() -> pd.Timestamp:
    """API-д хамгийн сүүлд бэлэн болсон өдрийг олно (ихэвчлэн өчигдөр/уржигдар)."""
    today = pd.Timestamp.today().normalize()
    probe = wiki.total_daily(today - pd.Timedelta(days=10), today, cache_dir=None)
    return probe["date"].max()


def fetch_many(titles, start, end, label):
    frames = []
    for i, t in enumerate(titles, 1):
        df = wiki.article_daily(t, start, end, cache_dir=CACHE)
        df["article"] = t
        frames.append(df)
        if i % 25 == 0 or i == len(titles):
            print(f"  [{label}] {i}/{len(titles)} татлаа")
    return pd.concat(frames, ignore_index=True)


def pick_viral_candidates(curated: set[str], end: pd.Timestamp) -> pd.DataFrame:
    """Сар бүрийн топ жагсаалтаас 1-2 сар л гарч ирсэн сэдвүүдийг нэр дэвшүүлнэ."""
    months = pd.period_range(START, end - pd.offsets.MonthBegin(1), freq="M")
    rows = []
    for p in months:
        top = wiki.top_articles(p.year, p.month, cache_dir=CACHE)
        top["month"] = str(p)
        rows.append(top)
    print(f"  {len(months)} сарын топ жагсаалт татлаа")
    allm = pd.concat(rows, ignore_index=True)
    allm = allm[allm["article"].map(wiki.is_real_article) & ~allm["article"].isin(curated)]

    g = allm.groupby("article").agg(
        n_months=("month", "nunique"), best_rank=("rank", "min"), peak_month=("month", "min")
    ).reset_index()
    # Богино хугацааны (1-2 сар) бөгөөд нэлээд өндөр байранд орсон сэдвүүд
    cand = g[(g["n_months"] <= 2) & (g["best_rank"] <= 300)].copy()
    cand["year"] = cand["peak_month"].str[:4]
    return cand


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    end = latest_available_day()
    print(f"Хугацаа: {START.date()} -> {end.date()}")

    # 1) Нийт хандалт
    total = wiki.total_daily(START, end, cache_dir=CACHE)
    total.to_parquet(OUT / "total_views.parquet", index=False)
    print(f"Нийт хандалт: {len(total)} өдөр")

    # 2) Сонгосон сэдвүүд
    arts = pd.read_csv(DATA / "articles.csv")
    curated = fetch_many(arts["article"].tolist(), START, end, "сонгосон")
    curated = curated.merge(arts, on="article", how="left")

    # 3) Вирал сэдвүүд: жил бүрээс тэнцүү шахуу санамсаргүй сонгоно
    cand = pick_viral_candidates(set(arts["article"]), end)
    rng = np.random.default_rng(SEED)
    per_year = int(np.ceil(N_VIRAL * 1.8 / cand["year"].nunique()))
    sampled = (
        cand.groupby("year", group_keys=False)
        .apply(lambda d: d.sample(min(len(d), per_year), random_state=int(rng.integers(1e9))))
    )
    print(f"Вирал нэр дэвшигч: {len(cand)}, түүвэр: {len(sampled)}")
    viral = fetch_many(sampled["article"].tolist(), START, end, "вирал")

    # Жинхэнэ "гэнэтийн" өсөлттэй эсэхийг шалгана: оргил / медиан >= VIRAL_MIN_RATIO
    stats = viral.groupby("article")["views"].agg(peak="max", median="median", n_days="count").reset_index()
    stats["ratio"] = stats["peak"] / stats["median"].clip(lower=1)
    keep = stats[(stats["ratio"] >= VIRAL_MIN_RATIO) & (stats["n_days"] >= 180)]
    keep = keep.sample(min(N_VIRAL, len(keep)), random_state=SEED)
    viral = viral[viral["article"].isin(keep["article"])].assign(category="viral")
    (sampled.merge(keep[["article", "ratio"]], on="article")
        .to_csv(DATA / "viral_articles.csv", index=False))
    print(f"Шүүлтийн дараа үлдсэн вирал сэдэв: {viral['article'].nunique()}")

    # 4) Нэгтгэж хадгална
    pv = pd.concat([curated, viral], ignore_index=True)
    pv["views"] = pv["views"].astype("int64")
    pv = pv[["date", "article", "category", "views"]].sort_values(["article", "date"])
    pv.to_parquet(OUT / "pageviews.parquet", index=False)
    print(f"Хадгаллаа: {len(pv):,} мөр, {pv['article'].nunique()} сэдэв -> data/processed/pageviews.parquet")


if __name__ == "__main__":
    main()
