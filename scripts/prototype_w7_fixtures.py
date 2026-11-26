"""PROTOTYPE — throwaway (W7, #52, 1-р шат: бүтэц). Main-д орохгүй.

Prototype-ийн хүнд тохиолдлуудад бодит snapshot-ууд: data/processed-ийг тухайн өдрөөр тасалж, сервертэй ижил кодоор
(src/serve.py) /api/trending, /api/map, /api/topic-ийн хариуг гаргаж app/static/prototype-w7/data/<тохиолдол>.json-д бичнэ.

Нэмэлт (prototype-д л, API-д байхгүй):
  - `anom`: сэдэв бүрийн сүүлийн 180 өдрийн Anomaly өдрүүд (src/anomaly.score, z ≥ 3) [{d, r}] — график ба spark дээрх ●.
  - `replay`: өнгөрсөн өдөр D (asof−3 … asof−REPLAY_MAX) бүрт тэр өдрийн snapshot-оор гаргасан таамаг (сэргээж тооцсон).
  - Тохиолдол бүрийг "шинэ өдөр" гэж харуулахын тулд today = asof + 1 (age_days 1, stale биш).

    python scripts/prototype_w7_fixtures.py            # ~5 минут
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import anomaly, live, serve, train  # noqa: E402

OUT = ROOT / "app" / "static" / "prototype-w7" / "data"
CASES = {
    "normal": "2026-11-10",      # cache-ийн сүүлийн бүрэн өдөр (Мягмар), ×10+ оргилтой сэдвүүд (Stephen Miller ×30, Nvidia ×24)
    "friday": "2026-11-06",      # Баасан гарагийн asof: "Бууралтаар" эрэмбэ, мөчлөгийн мөр
    "allfade": "2025-11-16",     # "үргэлжлэх" 0 (ADR 0020/0021: 19 anomaly, бүгд унтрах)
    "incomplete": "2026-11-09",  # "11.10 дутуу ирсэн" үед харуулах сүүлийн бүрэн өдөр (ADR 0022)
}
REPLAY_MIN, REPLAY_MAX = 3, 24
EXTRA_N = 15


def cut(raw: live.RawCache, d: pd.Timestamp) -> live.RawCache:
    return live.RawCache(raw.pageviews[raw.pageviews["date"] <= d], raw.alias[raw.alias["date"] <= d],
                         raw.total[raw.total["date"] <= d])


def anomaly_days(snap: serve.Snapshot, articles: set[str]) -> dict[str, list]:
    c = snap.clean[snap.clean["article"].isin(articles)]
    s = anomaly.score(c[["article", "date", "y", "attention", "views"]])
    c = c.assign(z=s["z"], anomaly=s["anomaly"], ratio=s["ratio"])
    c = c[c["anomaly"] & (c["date"] > snap.asof - pd.Timedelta(days=serve.TOPIC_DAYS))]
    out: dict[str, list] = {}
    for r in c.itertuples():
        out.setdefault(str(r.article), []).append({"d": r.date.strftime("%Y-%m-%d"),
                                                    "r": None if pd.isna(r.ratio) else round(float(r.ratio), 1)})
    return out


def build(model, raw: live.RawCache, asof: str) -> dict:
    a = pd.Timestamp(asof)
    today = a + pd.Timedelta(days=1)
    snap = serve.Snapshot.from_raw(cut(raw, a))
    tr = serve.trending(model, snap, today)
    mp = serve.attention_map(model, snap, today)
    items = tr["items"]
    by_pct = sorted((i for i in items if i["pct"] is not None), key=lambda i: i["pct"])
    keep = ({i["article"] for i in items if i["anomaly"] or i["rank"] is not None}
            | set(tr["cyclical_rise"]) | {i["article"] for i in mp["items"]}
            | {i["article"] for i in by_pct[:EXTRA_N]} | {i["article"] for i in by_pct[-EXTRA_N:]})
    anom = anomaly_days(snap, keep)
    for i in items:
        i["anom"] = [x for x in anom.get(i["article"], []) if x["d"] >= i["history"][0]["d"]]
    topics = {}
    for art in sorted(keep):
        t = serve.topic(model, snap, art, today)
        if t is not None:
            t["anom"] = anom.get(art, [])
            t["replay"] = []
            topics[art] = t
    for k in range(REPLAY_MIN, REPLAY_MAX + 1):
        d = a - pd.Timedelta(days=k)
        s = serve.Snapshot.from_raw(cut(raw, d))
        past = {i["article"]: i for i in serve.trending(model, s, d + pd.Timedelta(days=1))["items"]}
        for art, t in topics.items():
            p = past.get(art)
            if p is not None:
                t["replay"].append({"asof": d.strftime("%Y-%m-%d"), "forecast": p["forecast"], "pct": p["pct"],
                                    "interval": p["interval"], "anomaly": p["anomaly"], "verdict": p["verdict"]})
        print(f"  replay {d.date()}", flush=True)
    return {"case_asof": asof, "trending": tr, "map": mp, "topics": topics}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    model = train.load()
    raw = live.RawCache.load(ROOT / "data" / "processed")
    (OUT / "track_record.json").write_text(json.dumps(serve.track_records(model), ensure_ascii=False), encoding="utf-8")
    for name, asof in CASES.items():
        print(name, asof, flush=True)
        data = build(model, raw, asof)
        (OUT / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"  {name}: {len(data['topics'])} topics, anomalies {data['trending']['anomalies']}", flush=True)


if __name__ == "__main__":
    main()
