"""
Вэб backend-ийн inference (ADR 0008): cache-ийн өгөгдөл -> feature -> model -> scoring -> JSON.

Сургалттай ИЖИЛ код: цэвэрлэгээ нь `src/clean.clean_frame`, feature нь `src/features.make_features`,
тоо/шошго нь `src/scoring` (ADR 0003, 0004, 0005). Энд шинэ дүрэм зохиохгүй, зөвхөн JSON болгоно.

Feature-ийг сүүлийн FEATURE_DAYS өдрөөр тооцно: хамгийн урт цонх нь level_365 (365 хоног) тул asof өдрийн
утга бүтэн түүхээр тооцсонтой ижил (зөрүү ~1e-11). Бүх сэдвийн feature-ийг өгөгдлийн хувилбар бүрт нэг удаа
тооцож хадгална (`Snapshot.universe`). Model ба scoring нь хүсэлт бүрт ажиллана.

Санах ой (ADR 0012, Render 512 MB): цэвэрлэгээг (`clean_frame`) сэдэв бүрийн БҮТЭН түүх дээр хийнэ (trim, spike нь
бүтэн түүхээс хамаардаг), гэхдээ сэдвийн хэсгүүдээр (CHUNK_ARTICLES): алхам бүр сэдэв бүрээр бие даасан тул үр дүн
нэг дор цэвэрлэсэнтэй ижил. Хэсэг бүрээс Snapshot-д зөвхөн сүүлийн KEEP_DAYS өдрийг үлдээж, `/api/model`-д хэрэгтэй
бүтэн түүхийн тоог (`evaluate.HistoryStats`) тэр үед нь нэмж тооцно. Тиймээс хариу бүтэн түүхээр тооцсонтой ЯГ ижил.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import numpy as np
import pandas as pd

from src import clean, evaluate, features, scoring
from src.live import RawCache

FEATURE_DAYS = 366          # level_365-ийн цонх + asof
LIST_DAYS, TOPIC_DAYS = 30, 180
NORMAL_FROM, NORMAL_TO = 59, 7   # "ердийн өдөр" = t−59 … t−7 өдрийн уншилтын медиан (сүүлийн долоо хоногийг оруулахгүй)
MAP_N, CATEGORY_N = 40, 4
STALE_DAYS = 2                   # asof нь өнөөдрөөс 2-оос олон өдрийн өмнөх бол шар анхааруулга (ADR 0008)
# Snapshot-д барих өдөр: feature (level_365 + asof), /api/topic-ийн history, жагсаалт, "ердийн өдөр"-ийн хамгийн урт нь.
# Нөөц хэрэггүй: цэвэрлэгээ тайрахаас ӨМНӨ бүтэн түүхээр хийгдсэн тул тайрсан мөрийн утга өөрчлөгдөхгүй.
KEEP_DAYS = max(FEATURE_DAYS, TOPIC_DAYS, LIST_DAYS, NORMAL_FROM + 1)
CHUNK_ARTICLES = 40              # нэг удаа цэвэрлэх сэдвийн тоо (~70k мөр): Snapshot барих үеийн санах ойн оргил


@dataclass(eq=False)
class Snapshot:
    """Нэг хувилбарын цэвэр өгөгдөл. Сервер шинэ өгөгдөл ирэхэд бүхэлд нь сольдог (thread-д аюулгүй)."""
    clean: pd.DataFrame          # clean.COLS, зөвхөн сүүлийн KEEP_DAYS өдөр (asof-оос); index нь бүтэн хүснэгтийнх
    asof: pd.Timestamp
    history: dict | None = None  # evaluate.HistoryStats.result(): бүтэн түүхийн тоо (/api/model)
    built_at: pd.Timestamp = field(default_factory=lambda: pd.Timestamp.now(tz="UTC"))

    @classmethod
    def from_raw(cls, raw: RawCache, test_end: pd.Timestamp | None = None) -> "Snapshot":
        """test_end: /api/model-ийн түүхийн тоог тооцох сүүлийн өдөр (meta.json: test.test_end). None бол тооцохгүй."""
        since = raw.end - pd.Timedelta(days=KEEP_DAYS)
        acc = None if test_end is None else evaluate.HistoryStats(test_end)
        keep, offset = [], 0
        for cl in clean_chunks(raw):
            if acc is not None:
                acc.add(cl)
            cl.index += offset                 # бүтэн clean_frame-ийн index (сэдвүүд эрэмбээрээ залгагдана)
            offset += len(cl)
            keep.append(cl[cl["date"] > since].copy())
            del cl
        return cls(pd.concat(keep), raw.end, None if acc is None else acc.result())

    def tail(self, articles=None) -> pd.DataFrame:
        d = self.clean[self.clean["date"] > self.asof - pd.Timedelta(days=FEATURE_DAYS)]
        return d if articles is None else d[d["article"].isin(articles)]

    @cached_property
    def universe(self) -> pd.DataFrame:
        """Бүх сэдвийн asof өдрийн feature + measurable (нэг хувилбарт нэг удаа)."""
        return feature_rows(self.tail(), self.asof)


def clean_chunks(raw: RawCache, size: int = CHUNK_ARTICLES):
    """clean.clean_frame-ийг сэдвийн хэсгүүдээр: (article, date)-аар эрэмбэлсэн бүтэн үр дүнгийн дараалсан хэсгүүд."""
    pv_idx = raw.pageviews.groupby("article", sort=False).indices
    al_idx = raw.alias.groupby("article", sort=False).indices
    articles = sorted(pv_idx)
    for i in range(0, len(articles), size):
        part = articles[i:i + size]
        pv = raw.pageviews.take(np.concatenate([pv_idx[a] for a in part]))
        rows = [al_idx[a] for a in part if a in al_idx]
        al = raw.alias.take(np.concatenate(rows)) if rows else raw.alias.iloc[:0]
        cl, _ = clean.clean_frame(pv, al, raw.total, end=raw.end)
        yield cl


def feature_rows(tail: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """tail: clean.COLS-ийн сүүлийн FEATURE_DAYS. Буцаах: сэдэв бүрт asof өдрийн нэг мөр (feature, views, total, ...)."""
    f = features.make_features(tail[["date", "article", "category", "y"]])
    meas = scoring.is_measurable(tail[["article", "date", "y"]])
    extra = tail[["article", "date", "views", "total_views"]].assign(measurable=meas.to_numpy())
    f = f[f["date"] == asof].drop(columns=["category"]).merge(extra, on=["article", "date"], how="left")
    cat = tail.drop_duplicates("article").set_index("article")["category"].astype(object)
    f["category"] = f["article"].map(cat)
    normal = (tail[(tail["date"] >= asof - pd.Timedelta(days=NORMAL_FROM)) & (tail["date"] <= asof - pd.Timedelta(days=NORMAL_TO))]
              .groupby("article", observed=True)["views"].median())
    f["normal"] = f["article"].map(normal)
    f["article"] = f["article"].astype(object)
    return f.reset_index(drop=True)


def predict(model, rows: pd.DataFrame) -> pd.DataFrame:
    """rows: feature_rows. Model ажиллуулж h бүрийн Δ̂, pct, 80% интервал, уншилтын таамаг, сум нэмнэ.
    Feature дутуу (түүх богино) мөрийг хасна: сургалтад ийм мөр байгаагүй."""
    meta = model.meta
    r = rows.dropna(subset=meta["features"]).copy()
    y0 = r["y_0"].to_numpy()
    scale = (r["total_views"] / 1e6).to_numpy()     # анхаарал -> уншилт, asof өдрийн нийт уншилтаар
    for h in meta["horizons"]:
        q = meta["interval"][f"h{h}"]
        d = model.predict(r, h) if len(r) else np.array([])
        r[f"delta_hat_h{h}"] = d
        # таамаг, 80% интервалын доод/дээд хил (ADR 0003): pct ба уншилт
        for name, delta in (("", d), ("lo", d + q["lo"]), ("hi", d + q["hi"])):
            delta = scoring.floor_delta(y0, delta)
            # x_0 = 0 (asof өдөр 0 уншилт) бол x̂_h / x_0 − 1 = inf/NaN: хувь тодорхойгүй -> NaN.
            # Ингэснээр сум None, top-10-д орохгүй, JSON-д null (inf нь JSON биш тул сервер унадаг байсан).
            p = scoring.predicted_pct(y0, delta)
            r[f"{name or 'pct'}_h{h}"] = np.where(np.isfinite(p), p, np.nan)
            r[f"views{'_' + name if name else ''}_h{h}"] = np.expm1(y0 + delta) * scale
    r["arrow"] = scoring.arrow(r["pct_h3"], meta["fire"]["T"], r["measurable"])
    r["category"] = scoring.display_category(r["category"])
    return r


# ---------------------------------------------------------------- JSON

def _r(p: float) -> float | None:
    """5%-д дугуйлсан pct, JSON-д float-ын шуугиангүй (−0.15000000000000002 биш −0.15). Тодорхойгүй (NaN/inf) -> None."""
    if p is None or not np.isfinite(p):
        return None
    return round(scoring.round_pct(p), 2)


def md(d: pd.Timestamp) -> str:
    return f"{d.month}/{d.day}"


def forecast_dates(asof: pd.Timestamp) -> list[pd.Timestamp]:
    return [asof + pd.Timedelta(days=h) for h in (1, 2, 3)]


def dates_text(asof: pd.Timestamp) -> str:
    """Таамгийн тодорхой огноо (ADR 0008): "11/11–11/13"."""
    f = forecast_dates(asof)
    return f"{md(f[0])}–{md(f[-1])}"


def meta_block(asof: pd.Timestamp, today: pd.Timestamp) -> dict:
    age = int((pd.Timestamp(today).normalize() - asof).days)
    return {"asof": asof.strftime("%Y-%m-%d"), "mock": False, "dates": dates_text(asof),
            "age_days": age, "stale": age > STALE_DAYS}


def item(r, history: pd.DataFrame, asof: pd.Timestamp, rank: int | None = None) -> dict:
    """Нэг сэдвийн JSON. Хуучин бүтэц (article, title, category, views, ratio, history, forecast) хэвээр,
    дээр нь pct (h3, 5%-д дугуйлсан), 80% интервал, сум, 🔥, хэмжигдэх эсэх, огноо нэмэгдэнэ."""
    views = int(r.views)
    normal = float(r.normal) if pd.notna(r.normal) else views
    return {
        "article": r.article, "title": r.article.replace("_", " "), "category": r.category,
        "views": views, "ratio": round(views / max(normal, 1.0), 1),
        "history": [{"d": d.strftime("%Y-%m-%d"), "v": int(v)} for d, v in zip(history["date"], history["views"])],
        "forecast": [{"d": d.strftime("%Y-%m-%d"), "y": round(getattr(r, f"views_h{h}")),
                      "lo": round(getattr(r, f"views_lo_h{h}")), "hi": round(getattr(r, f"views_hi_h{h}")),
                      "pct": _r(getattr(r, f"pct_h{h}"))}
                     for h, d in zip((1, 2, 3), forecast_dates(asof))],
        "pct": _r(r.pct_h3), "pct_text": scoring.format_pct(r.pct_h3),
        "interval": {"lo": _r(r.lo_h3), "hi": _r(r.hi_h3)},
        "interval_text": scoring.interval_text(r.lo_h3, r.hi_h3),
        "arrow": r.arrow, "label": scoring.label(r.arrow, r.pct_h3),
        "fire": r.arrow == scoring.FIRE, "measurable": bool(r.measurable),
        "rank": rank, "dates": dates_text(asof),
    }


def _histories(snap: Snapshot, articles, days: int) -> dict[str, pd.DataFrame]:
    h = snap.clean[(snap.clean["date"] > snap.asof - pd.Timedelta(days=days)) & snap.clean["article"].isin(articles)]
    return {str(a): g for a, g in h.groupby("article", observed=True)}


def ranked(pred: pd.DataFrame) -> pd.DataFrame:
    """Top-10 (ADR 0004: хэмжигдэх сэдэв, таамагласан pct(h3)-ээр, үргэлж 10) эхэнд rank-тай, дараа нь бусад нь pct-ээр."""
    top = scoring.top10(pred, "pct_h3")
    rank = dict(zip(top["article"], top["rank"]))
    out = pred.assign(rank=pred["article"].map(rank))
    return out.sort_values(["rank", "pct_h3", "article"], ascending=[True, False, True], na_position="last")


def trending(model, snap: Snapshot, today) -> dict:
    """Нүүрний top-10 (эхний 10, rank 1…10) + "Бүх сэдэв" хуудасны бусад сэдвүүд."""
    p = ranked(predict(model, snap.universe))
    hist = _histories(snap, p["article"], LIST_DAYS)
    items = [item(r, hist[r.article], snap.asof, None if pd.isna(r.rank) else int(r.rank)) for r in p.itertuples()]
    return {**meta_block(snap.asof, today), "T": model.meta["fire"]["T"],
            "fires": sum(i["fire"] for i in items), "top_n": scoring.TOP_N, "items": items}


def categories(model, snap: Snapshot, today) -> dict:
    """Ангилал бүрийн хамгийн их уншигдсан CATEGORY_N сэдэв (вирал -> "Бусад")."""
    p = predict(model, snap.universe).sort_values(["views", "article"], ascending=[False, True])
    p = p.groupby("category", sort=False).head(CATEGORY_N)
    hist = _histories(snap, p["article"], LIST_DAYS)
    cats: dict[str, list] = {}
    for r in p.itertuples():
        cats.setdefault(r.category, []).append(item(r, hist[r.article], snap.asof))
    return {**meta_block(snap.asof, today), "categories": [{"key": k, "topics": v} for k, v in cats.items()]}


def attention_map(model, snap: Snapshot, today) -> dict:
    """Анхаарлын газрын зураг: asof өдөр хамгийн их уншигдсан MAP_N сэдэв."""
    p = predict(model, snap.universe)
    top = p.sort_values(["views", "article"], ascending=[False, True]).head(MAP_N)
    hist = _histories(snap, top["article"], 1)
    keep = ("article", "title", "category", "views", "ratio", "pct", "pct_text", "label", "arrow", "fire")
    return {**meta_block(snap.asof, today), "total_topics": int(len(p)), "total_views": int(p["views"].sum()),
            "items": [{k: v for k, v in item(r, hist[r.article], snap.asof).items() if k in keep} for r in top.itertuples()]}


def topic(model, snap: Snapshot, article: str, today) -> dict | None:
    """Нэг сэдэв: тэр сэдвийн feature-ийг хүсэлт бүрт тооцож, model ажиллуулна. Манай жагсаалтад байхгүй бол None."""
    tail = snap.tail([article])
    if tail.empty:
        return None
    p = predict(model, feature_rows(tail, snap.asof))
    if p.empty:
        return None
    r = next(p.itertuples())
    hist = _histories(snap, [article], TOPIC_DAYS)[article]
    return {**meta_block(snap.asof, today), **item(r, hist, snap.asof)}
