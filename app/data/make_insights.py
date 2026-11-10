"""
"Сонирхолтой" хуудасны баримтуудыг БОДИТ өгөгдлөөс тооцоолно.
Ажиллуулах:  python app/data/make_insights.py   ->  app/data/insights.json

Юуг харуулахыг (аль 2 ангилал, аль сар оргил, ямар хүрээ) энд сонгоно; сайт зөвхөн үг болгоно (app/static/words.js).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data" / "processed"
OUT = Path(__file__).resolve().parent / "insights.json"

# Карт бүр asof хүртэлх хэдэн хоногийг хардаг вэ (хоёр үзүүрээ оруулаад). Бусад карт: decay = бүх өгөгдөл, holidays = HOLIDAYS_FROM-оос
WINDOW_DAYS = {"categories": 30, "weekday": 730, "mongolia": 365}
HOLIDAYS = ["Halloween", "Christmas", "Valentine's_Day"]
HOLIDAYS_FROM = pd.Timestamp("2023-01-01")
WEEKDAY_SHOWN = 2        # гарагийн картад хэдэн ангилал харуулах вэ
DECAY_DAYS = 14          # оргилын дараах хэдэн өдрийг харах вэ
MONGOLIA_SHOWN = 6
ISO = "%Y-%m-%d"


def window(df: pd.DataFrame, end: pd.Timestamp, card: str) -> pd.DataFrame:
    """Картын хүрээнд орох мөрүүд: asof хүртэлх сүүлийн WINDOW_DAYS[card] хоног."""
    return df[df["date"] > end - pd.Timedelta(days=WINDOW_DAYS[card])]


def ranges(start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Карт бүрийн огнооны хүрээ (from, to хоёулаа орно). to = asof."""
    first = {card: end - pd.Timedelta(days=days - 1) for card, days in WINDOW_DAYS.items()}
    first.update(decay=start, holidays=HOLIDAYS_FROM)
    return {card: {"from": d.strftime(ISO), "to": end.strftime(ISO)} for card, d in first.items()}


def decay_curve(viral: pd.DataFrame) -> tuple[np.ndarray, int]:
    """Вирал сэдэв оргилын дараа хэр хурдан мартагддаг вэ (оргил = 100%): медиан муруй ба сэдвийн тоо."""
    curves = []
    for _, g in viral.groupby("article"):
        s = g.set_index("date")["views"].asfreq("D", fill_value=0)
        seg = s[s.idxmax(): s.idxmax() + pd.Timedelta(days=DECAY_DAYS)]
        if len(seg) == DECAY_DAYS + 1:
            curves.append(seg.values / s.max() * 100)
    return np.median(np.array(curves), axis=0), len(curves)


def weekday_index(curated: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    """Ангилал x гараг (0 = Даваа), 100 = долоо хоногийн дундаж. Медиан: нэг удаагийн огцом өсөлт нөлөөлөхгүй."""
    w = window(curated, end, "weekday").groupby(["date", "category"])["views"].sum().reset_index()
    w["dow"] = w["date"].dt.day_of_week
    idx = w.groupby(["category", "dow"])["views"].median().unstack()
    return (idx.div(idx.mean(axis=1), axis=0) * 100).round(1)


def weekday_pick(idx: pd.DataFrame) -> list[dict]:
    """Гарагийн хэлбэлзэл (max − min) хамгийн том WEEKDAY_SHOWN ангилал, тус бүрийн оргил ба хамгийн нам гараг.
    Тэнцвэл долоо хоногийн эхэнд ойр гараг (argmax/argmin эхнийхийг авна)."""
    swing = (idx.max(axis=1) - idx.min(axis=1)).sort_values(ascending=False, kind="stable")
    return [{"key": k, "peak": int(np.argmax(idx.loc[k].values)), "low": int(np.argmin(idx.loc[k].values))}
            for k in swing.index[:WEEKDAY_SHOWN]]


def holiday_monthly(pv: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    """Баярын нийтлэлүүдийн сар бүрийн өдрийн дундаж уншилт; дуусаагүй сарыг хасна."""
    hol = (pv[pv["article"].isin(HOLIDAYS) & (pv["date"] >= HOLIDAYS_FROM)]
           .set_index("date").groupby("article")["views"].resample("MS").mean().unstack(0))
    return hol[hol.index < end.to_period("M").to_timestamp()]


def holiday_peaks(hol: pd.DataFrame) -> dict:
    """Бүтэн жилүүд (12 сар нь бүгд байгаа), дутуу сүүлийн жил, цуваа бүрийн сүүлийн бүтэн жилийн оргил сар."""
    months = hol.index.year.value_counts()
    full = sorted(int(y) for y, n in months.items() if n == 12)
    last_year = int(hol.index.year.max())
    last_full = hol[hol.index.year == full[-1]]
    return {
        "full_years": full,
        "incomplete_year": None if last_year in full else last_year,
        "peaks": {a: last_full[a].idxmax().strftime("%Y-%m") for a in hol.columns},
    }


def load() -> pd.DataFrame:
    pv = pd.read_parquet(P / "pageviews.parquet")
    # Нэр солигдсон нийтлэлийн хуучин нэрийн уншилтыг шинэ нэрэнд нэмнэ
    al = pd.read_parquet(P / "alias_pageviews.parquet")
    cat = pv.drop_duplicates("article").set_index("article")["category"]
    al["category"] = al["article"].map(cat)
    return (pd.concat([pv, al[["date", "article", "category", "views"]]])
              .groupby(["date", "article", "category"], as_index=False)["views"].sum())


def title(article: str) -> str:
    return article.replace("_", " ")


def build(pv: pd.DataFrame) -> dict:
    end = pv["date"].max()
    curated = pv[pv["category"] != "viral"]

    decay, decay_n = decay_curve(pv[pv["category"] == "viral"])
    by_cat = window(curated, end, "categories").groupby("category")["views"].sum().sort_values(ascending=False)
    idx = weekday_index(curated, end)
    hol = holiday_monthly(pv, end)
    mongolia = curated[curated["category"] == "mongolia"]
    mn = window(mongolia, end, "mongolia").groupby("article")["views"].sum().sort_values(ascending=False)
    mn_share = mn / mn.sum() * 100
    peaks = holiday_peaks(hol)
    peaks["peaks"] = {title(a): m for a, m in peaks["peaks"].items()}

    return {
        "asof": end.strftime(ISO),
        "ranges": ranges(pv["date"].min(), end),
        "topics_n": int(pv["article"].nunique()),
        "curated_n": int(curated["article"].nunique()),
        "mongolia_n": int(mongolia["article"].nunique()),
        "decay": [round(float(x), 1) for x in decay],
        "decay_n": decay_n,
        "categories": [{"key": k, "views": int(v)} for k, v in by_cat.items()],
        "weekday": {k: [float(x) for x in idx.loc[k].values] for k in idx.index},
        "weekday_pick": weekday_pick(idx),
        "holidays": {
            "months": [d.strftime("%Y-%m") for d in hol.index],
            "series": {title(a): [int(round(x)) for x in hol[a].fillna(0).values] for a in hol.columns},
            **peaks,
        },
        "mongolia": [{"title": title(a), "share": round(float(s), 1)} for a, s in mn_share.head(MONGOLIA_SHOWN).items()],
    }


if __name__ == "__main__":
    out = build(load())
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("insights.json:", {k: (len(v) if hasattr(v, "__len__") else v) for k, v in out.items()})
