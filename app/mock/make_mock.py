"""
ТҮР ЗУУРЫН жишээ өгөгдөл үүсгэгч.
Model бэлэн болохоос өмнө вэбийн дизайныг турших зорилготой.
Бодит түүх (cache-д татагдсан сэдвүүд) + ХУУРАМЧ таамаг ашиглана.
Model бэлэн болмогц app/main.py бодит таамгийг өгөх тул энэ файлыг устгана.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
rng = np.random.default_rng(7)

pv = pd.read_parquet(ROOT / "data" / "processed" / "pageviews.parquet")
cat_of = dict(zip(pv["article"], pv["category"]))
series = {a: g.set_index("date")["views"] for a, g in pv.groupby("article")}

end = max(s.index.max() for s in series.values())


def topic(article, days=30):
    s = series[article].reindex(pd.date_range(end - pd.Timedelta(days=364), end), fill_value=0)
    base = float(s.iloc[-60:-7].median()) or 1.0
    last = float(s.iloc[-1])
    # Хуурамч таамаг: сүүлийн утгаас медиан руу буцах + санамсаргүй хэлбэлзэл
    yhat, lo, hi = [], [], []
    for h in (1, 2, 3):
        mu = base + (last - base) * 0.55**h * rng.uniform(0.8, 1.2)
        yhat.append(round(mu)); lo.append(round(mu * 0.72)); hi.append(round(mu * 1.38))
    fdates = pd.date_range(end + pd.Timedelta(days=1), periods=3)
    return {
        "article": article,
        "title": article.replace("_", " "),
        "category": cat_of.get(article, "viral"),
        "views": int(last),
        "ratio": round(last / base, 1),
        "history": [{"d": d.strftime("%Y-%m-%d"), "v": int(v)} for d, v in s.iloc[-days:].items()],
        "forecast": [{"d": d.strftime("%Y-%m-%d"), "y": y, "lo": l, "hi": u}
                     for d, y, l, u in zip(fdates, yhat, lo, hi)],
    }


all_t = [topic(a) for a in series]
trending = sorted(all_t, key=lambda t: t["views"], reverse=True)[:20]
# Шуугианы жагсаалтад өсөлтийн харьцааг хамгийн их нэрсийг дээр гаргая
trending = sorted(trending, key=lambda t: t["ratio"], reverse=True)

cats = {}
for t in all_t:
    cats.setdefault(t["category"], []).append(t)
categories = [{"key": k, "topics": sorted(v, key=lambda t: t["views"], reverse=True)[:4]} for k, v in cats.items()]

meta = {"asof": end.strftime("%Y-%m-%d"), "mock": True}
# Анхаарлын газрын зураг: өчигдөр хамгийн их уншигдсан 40 сэдэв (хэмжээ = уншилт, өнгө = өсөлт)
mapped = sorted(all_t, key=lambda t: t["views"], reverse=True)[:40]
json.dump({**meta, "total_topics": len(all_t), "total_views": int(sum(t["views"] for t in all_t)),
           "items": [{k: t[k] for k in ("article", "title", "category", "views", "ratio")} for t in mapped]},
          open(OUT / "map.json", "w"), ensure_ascii=False)
json.dump({**meta, "items": trending}, open(OUT / "trending.json", "w"), ensure_ascii=False)
json.dump({**meta, "categories": categories}, open(OUT / "categories.json", "w"), ensure_ascii=False)
topics = {a: topic(a, days=180) for a in series}
json.dump({**meta, "topics": topics}, open(OUT / "topics.json", "w"), ensure_ascii=False)

model = {
    **meta,
    "metrics": [
        {"h": 1, "model": 0.21, "naive": 0.29, "seasonal": 0.34},
        {"h": 2, "model": 0.27, "naive": 0.38, "seasonal": 0.40},
        {"h": 3, "model": 0.31, "naive": 0.45, "seasonal": 0.44},
    ],
    "curve": [{"it": i, "train": round(0.9 * np.exp(-i / 120) + 0.17, 3),
               "valid": round(0.9 * np.exp(-i / 140) + 0.22 + max(0, i - 420) * 0.00008, 3)}
              for i in range(0, 801, 20)],
    "best_iter": 420,
    "importance": [{"f": f, "gain": g} for f, g in [
        ("lag_1", 41), ("ratio_7", 17), ("roll_mean_7", 12), ("lag_7", 8), ("growth_3", 6),
        ("dow", 5), ("roll_std_14", 4), ("category", 3), ("lag_14", 2), ("days_since_peak", 2)]],
}
json.dump(model, open(OUT / "model.json", "w"), ensure_ascii=False)
print(f"mock: {len(series)} сэдэв, asof {meta['asof']}")
