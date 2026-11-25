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

import json
from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from src import anomaly, clean, cycle, evaluate, features, scoring, situation, train
from src.live import RawCache

FEATURE_DAYS = 366          # level_365-ийн цонх + asof
LIST_DAYS, TOPIC_DAYS = 30, 180
MAP_N, CATEGORY_N = 40, 4
STALE_DAYS = 2                   # asof нь өнөөдрөөс 2-оос олон өдрийн өмнөх бол шар анхааруулга (ADR 0008)
# Snapshot-д барих өдөр: feature (level_365 + asof), /api/topic-ийн history, жагсаалт, anomaly-ийн цонх (t−59 … t−7)
# сүүлийн 7 хоногийн оргилын z-д (t−7-ийн цонх t−66 хүртэл, ADR 0020), мөчлөг (t−28 … t−4)-ийн хамгийн урт нь.
# Нөөц хэрэггүй: цэвэрлэгээ тайрахаас ӨМНӨ бүтэн түүхээр хийгдсэн тул тайрсан мөрийн утга өөрчлөгдөхгүй.
PEAK_FROM = anomaly.WINDOW_FROM + situation.PEAK_DAYS   # t−7 өдрийн z-ийн цонх t−66-аас эхэлнэ
KEEP_DAYS = max(FEATURE_DAYS, TOPIC_DAYS, LIST_DAYS, PEAK_FROM + 1, cycle.HISTORY_DAYS + 1)
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

    @cached_property
    def total_note(self) -> dict | None:
        """asof өдөр Wikipedia-ийн нийт уншилт ердийнхөөс огцом зөрсөн бол өдрийн мөр (ADR 0017), үгүй бол None."""
        return anomaly.total_note(self.clean.drop_duplicates("date")[["date", "total_views"]], self.asof)


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
    # Anomaly (ADR 0017): z, ×N (анхаарал), ердийн өдрийн уншилт гэх мэт. asof өдрийнхөд t−59 … asof хангалттай,
    # сүүлийн 7 хоногийн оргил (ADR 0020, t−7 … t−1 өдрийн z) нь t−66-аас. asof өдрийн z цонхоосоо л хамаарна.
    recent = tail[tail["date"] >= asof - pd.Timedelta(days=PEAK_FROM)]
    scored = anomaly.score(recent)
    peak = situation.recent_peak(recent[["article", "date", "y"]].assign(z=scored["z"].to_numpy()))
    at = (recent["date"] == asof).to_numpy()
    an = pd.concat([scored, peak], axis=1)[at]
    an = an.set_index(recent.loc[an.index, "article"].astype(object))
    for c in an.columns:
        f[c] = f["article"].astype(object).map(an[c])
    # Нийт уншилтын нөлөө (ADR 0020): asof өдрийн нийт уншилт ердийнхөөс огцом зөрсөн (Snapshot.total_note-тэй ижил дүрэм)
    f["total_day"] = anomaly.total_note(tail.drop_duplicates("date")[["date", "total_views"]], asof) is not None
    # Мөчлөг (ADR 0019): asof өдрийнхөд t−28 … t−4 хангалттай
    weeks = tail[tail["date"] >= asof - pd.Timedelta(days=cycle.HISTORY_DAYS)]
    cyc = cycle.cycle(weeks)[(weeks["date"] == asof).to_numpy()]
    f["cycle"] = f["article"].astype(object).map(pd.Series(cyc.to_numpy(), index=weeks.loc[cyc.index, "article"].astype(object)))
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
    # Илүүдэл ба мөчлөгийн өсөлт/бууралт (ADR 0019), таамагласан pct (h3) дээр
    r["excess"] = cycle.excess(r["pct_h3"], r["cycle"])
    r["cyclical"] = cycle.is_cyclical_rise(r["pct_h3"], r["cycle"]) | cycle.is_cyclical_fall(r["pct_h3"], r["cycle"])
    # Нөхцөл байдлын код (ADR 0020) ба Anomaly-ийн дүгнэлт (ADR 0021), src/situation.py
    r["situation"] = situation.code(r)
    r["verdict"] = pd.Series(situation.verdict(r["pct_h3"], r["anomaly"]), index=r.index, dtype=object)   # None хэвээр (str dtype NaN болгоно)
    r["category"] = scoring.display_category(r["category"])
    return r


# ---------------------------------------------------------------- JSON

def _r(p: float) -> float | None:
    """5%-ийн алхмаар тэг рүү тайрсан pct (scoring.round_pct), JSON-д float-ын шуугиангүй (−0.15000000000000002 биш −0.15). Тодорхойгүй (NaN/inf) -> None."""
    if p is None or not np.isfinite(p):
        return None
    return round(scoring.round_pct(p), 2)


def md(d: pd.Timestamp) -> str:
    """Сайтын богино огноо (ADR 0018): сар.өдөр, тэгээр нөхсөн ("11.09"). Frontend-ийн Words.md-тэй ижил."""
    return f"{d.month:02d}.{d.day:02d}"


def forecast_dates(asof: pd.Timestamp) -> list[pd.Timestamp]:
    return [asof + pd.Timedelta(days=h) for h in (1, 2, 3)]


def dates_text(asof: pd.Timestamp) -> str:
    """Таамгийн тодорхой огноо (ADR 0008, 0018): "11.11–11.13"."""
    f = forecast_dates(asof)
    return f"{md(f[0])}–{md(f[-1])}"


def meta_block(asof: pd.Timestamp, today: pd.Timestamp) -> dict:
    age = int((pd.Timestamp(today).normalize() - asof).days)
    return {"asof": asof.strftime("%Y-%m-%d"), "mock": False, "dates": dates_text(asof),
            "age_days": age, "stale": age > STALE_DAYS}


def day_block(snap: Snapshot, today: pd.Timestamp) -> dict:
    """Сэдвийн хариуны толгой: meta_block + нийт уншилтын өдрийн мөр (`total_note`, ихэнх өдөр null)."""
    return {**meta_block(snap.asof, today), "total_note": snap.total_note}


def _num(v, digits: int) -> float | None:
    """JSON-д тоо, тодорхойгүй (NaN/inf) бол null."""
    return round(float(v), digits) if v is not None and np.isfinite(v) else None


# ---------------------------------------------------------------- track record (ADR 0020, 0021)
TRACK_FILE = Path(__file__).resolve().parents[1] / "app" / "data" / "track_record.json"   # python -m src.track_record build


@lru_cache(maxsize=4)
def _track_file(path: Path) -> dict | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def track_records(model, path: Path | None = None) -> dict:
    """/api/track-record: эх сурвалж бүрийн хүснэгт (src/situation.track_record), ачаалсан model-ийн хувилбар мөн эсэх (`current`)."""
    data = _track_file(TRACK_FILE if path is None else path) or {"sources": []}
    version = train.short_version(model.model_hash)
    return {"model_version": version, "min_n": situation.MIN_N,
            "sources": [{**s, "current": s["model_hash"] == model.model_hash} for s in data["sources"]]}


def verdict_tracks(model, path: Path | None = None) -> dict[str, dict]:
    """Дүгнэлт бүрийн track record: ачаалсан model хувилбарын СЭРГЭЭЖ ТООЦСОН хүснэгтээс (хадгалсан нь тусдаа, холихгүй).
    Тийм хүснэгт алга бол хоосон (item-д null)."""
    src = next((s for s in track_records(model, path)["sources"] if s["current"] and s["source_key"] == "recomputed"), None)
    if src is None:
        return {}
    keep = ("n", "enough", "text", "hit", "base_hit")   # text = "хангалтгүй" (n < 20)
    return {e["key"]: {"source": src["source"], "model_version": src["model_version"], **{k: e[k] for k in keep if k in e}}
            for e in src["by_verdict"]}


def item(r, history: pd.DataFrame, asof: pd.Timestamp, rank: int | None = None, tracks: dict | None = None) -> dict:
    """Нэг сэдвийн JSON. Хуучин бүтэц (article, title, category, views, ratio, history, forecast) хэвээр,
    дээр нь pct (h3, 5%-д дугуйлсан), 80% интервал, сум, 🔥, хэмжигдэх эсэх, огноо нэмэгдэнэ.
    Anomaly (ADR 0017, src/anomaly.py): `ratio` = ▲ ×N АНХААРАЛ дээр, `views_ratio` = түүхий уншилтын ×N (хаалтанд),
    `normal` = ердийн өдрийн уншилт, `z`/`anomaly` (z ≥ 3), `typical_pct` = ердийн хэлбэлзэл ±, `similar_days` = сүүлийн
    2 сард (t−59 … t−7) ийм өндөр өдрийн тоо.
    Мөчлөг (ADR 0019, src/cycle.py): `cycle` = долоо хоногийн мөчлөг (h3), `excess` = таамгийн илүүдэл (хоёулаа pct шиг
    5%-ийн алхмаар тэг рүү тайрсан тул ±10%-ийн хил хадгалагдана), `cyclical` = мөчлөгийн өсөлт эсвэл бууралт.
    Нөхцөл байдал (ADR 0020, src/situation.py): `situation` = код, `situation_label` = нэр. Anomaly-д л (ADR 0021): `verdict` =
    "continue"/"fade", `verdict_label` = "үргэлжлэх"/"унтрах", `verdict_track` = тэр дүгнэлтийн track record (tracks-аас)."""
    normal = _num(r.normal, 0)
    v = r.verdict
    return {
        "article": r.article, "title": r.article.replace("_", " "), "category": r.category,
        "views": int(r.views), "ratio": _num(r.ratio, 1), "views_ratio": _num(r.views_ratio, 1),
        "normal": None if normal is None else int(normal),
        "z": _num(r.z, 2), "anomaly": bool(r.anomaly), "typical_pct": _num(r.typical_pct, 2),
        "similar_days": int(r.similar_days),
        "cycle": _r(r.cycle), "excess": _r(r.excess), "cyclical": bool(r.cyclical),
        "situation": r.situation, "situation_label": situation.CODES[r.situation],
        "verdict": v, "verdict_label": None if v is None else situation.VERDICTS[v],
        "verdict_track": None if v is None else (tracks or {}).get(v),
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
    """Давж өсөх жагсаалт (ADR 0019: хэмжигдэх, мөчлөгийн өсөлт биш Rising, pct(h3)-ээр, ≤ 10) эхэнд rank-тай,
    дараа нь мөчлөгийн өсөлтүүд (`cyclical_rank`), дараа нь бусад нь pct-ээр."""
    rank = lambda lst: pred["article"].map(dict(zip(lst["article"], lst["rank"])))   # noqa: E731
    out = pred.assign(rank=rank(cycle.beyond_list(pred, "pct_h3")), cyclical_rank=rank(cycle.cyclical_rise_list(pred, "pct_h3")))
    return out.sort_values(["rank", "cyclical_rank", "pct_h3", "article"], ascending=[True, True, False, True], na_position="last")


def anomaly_summary(items: list[dict]) -> dict:
    """asof өдрийн Anomaly-ууд дүгнэлтээр (ADR 0021). all_fade: Anomaly байгаа ч "үргэлжлэх" 0 (valid дээр 271-ээс 8 өдөр):
    нүүр хоосон болохгүй, anomaly-ууд "унтрах" дүгнэлттэй хэвээр харагдана."""
    v = [i["verdict"] for i in items if i["verdict"]]
    k = v.count("continue")
    return {"n": len(v), "continue": k, "fade": len(v) - k, "all_fade": bool(v) and k == 0}


def trending(model, snap: Snapshot, today) -> dict:
    """Нүүрний Давж өсөх жагсаалт (эхэнд, rank 1…≤10; `beyond`), Мөчлөгийн өсөлтийн жагсаалт (`cyclical_rise`)
    + "Бүх сэдэв" хуудасны бусад сэдвүүд. `fires` нь Давж өсөх жагсаалтын 🔥."""
    p = ranked(predict(model, snap.universe))
    hist = _histories(snap, p["article"], LIST_DAYS)
    tracks = verdict_tracks(model)
    items = [item(r, hist[r.article], snap.asof, None if pd.isna(r.rank) else int(r.rank), tracks) for r in p.itertuples()]
    beyond = [i for i in items if i["rank"] is not None]
    return {**day_block(snap, today), "T": model.meta["fire"]["T"], "anomalies": anomaly_summary(items),
            "fires": sum(i["fire"] for i in beyond), "top_n": scoring.TOP_N,
            "beyond": [i["article"] for i in beyond],
            "cyclical_rise": p.loc[p["cyclical_rank"].notna(), "article"].tolist(), "items": items}


def categories(model, snap: Snapshot, today) -> dict:
    """Ангилал бүрийн хамгийн их уншигдсан CATEGORY_N сэдэв (вирал -> "Бусад")."""
    p = predict(model, snap.universe).sort_values(["views", "article"], ascending=[False, True])
    p = p.groupby("category", sort=False).head(CATEGORY_N)
    hist = _histories(snap, p["article"], LIST_DAYS)
    tracks = verdict_tracks(model)
    cats: dict[str, list] = {}
    for r in p.itertuples():
        cats.setdefault(r.category, []).append(item(r, hist[r.article], snap.asof, tracks=tracks))
    return {**day_block(snap, today), "categories": [{"key": k, "topics": v} for k, v in cats.items()]}


def attention_map(model, snap: Snapshot, today) -> dict:
    """Анхаарлын газрын зураг: asof өдөр хамгийн их уншигдсан MAP_N сэдэв."""
    p = predict(model, snap.universe)
    top = p.sort_values(["views", "article"], ascending=[False, True]).head(MAP_N)
    hist = _histories(snap, top["article"], 1)
    keep = ("article", "title", "category", "views", "ratio", "views_ratio", "anomaly", "pct", "pct_text", "label", "arrow", "fire")
    return {**day_block(snap, today), "total_topics": int(len(p)), "total_views": int(p["views"].sum()),
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
    return {**day_block(snap, today), **item(r, hist, snap.asof, tracks=verdict_tracks(model))}
