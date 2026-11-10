"""
"Сонирхолтой" хуудасны баримтуудыг БОДИТ өгөгдлөөс тооцоолно.
Ажиллуулах:  python app/data/make_insights.py   ->  app/data/insights.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data" / "processed"

pv = pd.read_parquet(P / "pageviews.parquet")
# Нэр солигдсон нийтлэлийн хуучин нэрийн уншилтыг шинэ нэрэнд нэмнэ
al = pd.read_parquet(P / "alias_pageviews.parquet")
cat = pv.drop_duplicates("article").set_index("article")["category"]
al["category"] = al["article"].map(cat)
pv = (pd.concat([pv, al[["date", "article", "category", "views"]]])
        .groupby(["date", "article", "category"], as_index=False)["views"].sum())
end = pv["date"].max()
curated = pv[pv["category"] != "viral"]

# 1) Вирал сэдэв оргилын дараа хэр хурдан мартагддаг вэ (оргил = 100%)
curves = []
for _, g in pv[pv["category"] == "viral"].groupby("article"):
    s = g.set_index("date")["views"].asfreq("D", fill_value=0)
    seg = s[s.idxmax(): s.idxmax() + pd.Timedelta(days=14)]
    if len(seg) == 15:
        curves.append(seg.values / s.max() * 100)
decay = np.median(np.array(curves), axis=0)

# 2) Сүүлийн 30 хоногт ангилал бүр нийт хэдэн удаа уншигдсан бэ
last30 = (curated[curated["date"] > end - pd.Timedelta(days=30)]
          .groupby("category")["views"].sum().sort_values(ascending=False))

# 3) Гарагийн хэв маяг (сүүлийн 2 жил, медиан ашиглана -> нэг удаагийн огцом өсөлт нөлөөлөхгүй)
w = (curated[curated["date"] > end - pd.Timedelta(days=730)]
     .groupby(["date", "category"])["views"].sum().reset_index())
w["dow"] = w["date"].dt.dayofweek
idx = w.groupby(["category", "dow"])["views"].median().unstack()
idx = idx.div(idx.mean(axis=1), axis=0) * 100

# 4) Баярын өдрүүдийн жил бүрийн давталт (сар бүрийн өдрийн дундаж)
hol = (pv[pv["article"].isin(["Halloween", "Christmas", "Valentine's_Day"]) & (pv["date"] >= "2023-01-01")]
       .set_index("date").groupby("article")["views"].resample("MS").mean().unstack(0))
hol = hol[hol.index < end.to_period("M").to_timestamp()]  # дуусаагүй сарыг хасна

# 5) Монголын сэдвүүдээс аль нь хамгийн их уншигддаг вэ (сүүлийн 1 жил)
mn = (curated[(curated["category"] == "mongolia") & (curated["date"] > end - pd.Timedelta(days=365))]
      .groupby("article")["views"].sum().sort_values(ascending=False))
mn_share = (mn / mn.sum() * 100)

out = {
    "asof": end.strftime("%Y-%m-%d"),
    "decay": [round(float(x), 1) for x in decay],
    "decay_n": len(curves),
    "categories": [{"key": k, "views": int(v)} for k, v in last30.items()],
    "weekday": {k: [round(float(x), 1) for x in idx.loc[k].values] for k in idx.index},
    "holidays": {
        "months": [d.strftime("%Y-%m") for d in hol.index],
        "series": {a.replace("_", " "): [int(round(x)) for x in hol[a].fillna(0).values] for a in hol.columns},
    },
    "mongolia": [{"title": a.replace("_", " "), "share": round(float(s), 1)} for a, s in mn_share.head(6).items()],
}
(Path(__file__).resolve().parent / "insights.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print("insights.json:", {k: (len(v) if hasattr(v, "__len__") else v) for k, v in out.items()})
