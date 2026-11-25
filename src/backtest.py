"""
Сэргээж тооцсон таамгийн backtest (ADR 0015, #50).

As-of replay: asof D бүрт түүхий өгөгдлийг ≤ D хүртэл тайраад сервертэй ИЖИЛ замаар (`serve.Snapshot.from_raw` ->
`serve.predict`) тооцно. Бэлэн цэвэрлэсэн хүснэгтээс (`clean.parquet`) тооцохгүй: `clean.cap_isolated_spikes` нь t+1 өдрийн
утга ба төвлөрсөн 29 хоногийн медиан ашигладаг (look-ahead).

Ажиллуулах (~4 сек/өдөр, ~230 өдөр ≈ 15 минут; background-д болно, тасарвал дахин ажиллуулахад тооцсон өдрөө алгасна):
    python -m src.backtest run                      # хилээс data/processed-ийн сүүлийн өдөр хүртэл
    nohup python -m src.backtest run > backtest.log 2>&1 &

Гаралт: data/backtest/<model хувилбар>/
    backtest.parquet   asof × сэдэв: таамаг (h1–h3 Δ̂, pct, 80% интервал, уншилт), бодит утга, бүлэг, model_hash
    summary.json       бүлгээр (гол нь (а)) MAE/skill/интервалын хамралт + үлдэх хазайлт
Хувилбар бүр өөрийн хавтастай, файл доторх model_hash өөр бол ажиллахгүй: өөр хувилбарын үр дүнг холихгүй.

Бодит утга: D+h өдрийн y-г ОДООГИЙН бүтэн өгөгдлөөр цэвэрлэсэн хүснэгтээс (бот-ын тусгаарлагдсан өсөлтийг хязгаарласан),
суурь нь тэр өдөр харагдах байсан as-of y_0: Δ = y_{D+h} − y_0, pct = x_{D+h} / x_0 − 1. evaluate.py-ийн test-ээс ЯЛГААТАЙ
(тэнд y_0 нь мөн бүтэн өгөгдлөөр цэвэрлэсэн): таамаг "өнөөдөр x_0 харагдаж байна, h өдрийн дараа ..." гэж хэлдэг тул суурь нь
харагдсан x_0. D өдрийн бот-ын өсөлт as-of-д хязгаарлагддаггүй (t+1 алга) тул ийм өдөр бодит Δ их уналттай гарна.
Өгөгдөл нэмэгдэх бүрд дахин тооцогдоно (таамаг кэшлэгдэнэ, бодит утга үгүй). data/processed-ийн өнгөрсөн өдрүүдийг дахин
татаж засварласан бол тэр хувилбарын хавтсыг устгаад дахин тооцно.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src import evaluate, live, scoring, serve, train

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "backtest"

# ---------------------------------------------------------------- хил (ADR 0015, 1-р дүрэм)
# Хил = тэр model хувилбарын сургалт/сонголт/калибровкт ашигласан сүүлийн өдрийн ДАРААГИЙН өдөр. Одоогийн model:
# сургалт ≤ 2025-06-30, early stopping/сонголт/T/интервал нь valid (≤ 2026-03-31) -> хил = test-ийн эхний өдөр 2026-04-01.
# Model-ийг дахин сургавал эсвэл src/calibrate.py meta.json-ийг дахин бичвэл hash өөрчлөгдөнө: тэр үед FROM-ыг шинэ
# хувилбарын сүүлийн ашигласан өдрийн дараагийн өдөр болгож, FROM_MODEL_HASH-ийг `train.model_hash()`-аар шинэчил.
FROM = pd.Timestamp("2026-04-01")
FROM_MODEL_HASH = "82e4bf3a2c14a8156b570b5cc931270cc1949610c23286ce6742b14d73d24cfc"


class BoundaryOutdated(RuntimeError):
    """Ачаалсан model нь FROM-ыг тогтоосон хувилбар биш."""


def boundary(model) -> pd.Timestamp:
    """Backtest-ийн эхний asof. Model хувилбар FROM_MODEL_HASH биш бол BoundaryOutdated (хилийг шинэчлэх ёстой)."""
    if model.model_hash != FROM_MODEL_HASH:
        raise BoundaryOutdated(
            f"model {train.short_version(model.model_hash)} нь хил {FROM.date()}-ийг тогтоосон "
            f"{train.short_version(FROM_MODEL_HASH)} биш. Дахин сургасан/калибровк хийсэн бол хилийг (src/backtest.py: FROM, "
            "FROM_MODEL_HASH) тэр хувилбарын сургалт/сонголт/калибровкт ашигласан сүүлийн өдрийн дараагийн өдөр болго (ADR 0015).")
    return FROM


HORIZONS = (1, 2, 3)
PRED_COLS = ["delta_hat", "pct", "lo", "hi", "views"]   # h бүрт: Δ̂, таамагласан pct, 80% интервал (pct), уншилтын таамаг


def truncate(raw: live.RawCache, asof: pd.Timestamp) -> live.RawCache:
    """D хүртэлх (D орно) түүхий өгөгдөл: сервер D+1-нд яг үүнийг харна (Wikimedia D өдрийг D+1-нд гаргадаг)."""
    upto = lambda df: df[df["date"] <= asof].reset_index(drop=True)   # noqa: E731
    return live.RawCache(upto(raw.pageviews), upto(raw.alias), upto(raw.total))


def replay(raw: live.RawCache, model, asof) -> pd.DataFrame:
    """asof D-ийн сэргээж тооцсон таамаг: таамагласан сэдэв бүрт нэг мөр (feature дутуу сэдэв орохгүй, сервертэй адил).
    Баганууд: asof, article, category (сайтын), was_missing (D өдөр сэдвийн үндсэн нэрийн мөр алга), views, y_0,
    measurable, arrow, h бүрт `{delta_hat,pct,lo,hi,views}_h{h}`."""
    asof = pd.Timestamp(asof)
    cut = truncate(raw, asof)
    if cut.end != asof:
        raise ValueError(f"{asof.date()} өдрийн total_views алга (өгөгдөл {cut.end.date()} хүртэл)")
    pred = serve.predict(model, serve.Snapshot.from_raw(cut).universe)
    arrived = set(cut.pageviews.loc[cut.pageviews["date"] == asof, "article"])
    out = pd.DataFrame({
        "asof": asof, "article": pred["article"].astype(str), "category": pred["category"].astype(str),
        "was_missing": ~pred["article"].isin(arrived), "views": pred["views"].astype("int64"),
        "y_0": pred["y_0"].astype(float), "measurable": pred["measurable"].astype(bool), "arrow": pred["arrow"]})
    for h in HORIZONS:
        for c in PRED_COLS:
            out[f"{c}_h{h}"] = pred[f"{c}_h{h}"].astype(float)
    return out.sort_values("article").reset_index(drop=True)


# ---------------------------------------------------------------- бүх өдөр

FILE, SUMMARY = "backtest.parquet", "summary.json"
SOURCE = "сэргээж тооцсон"   # GLOSSARY: Сэргээж тооцсон таамаг (хадгалсан таамагтай холихгүй, ADR 0015/0016)
ACTUAL_COLS = ["actual_delta", "actual_pct", "actual_views"]
CAVEATS = [
    ("Сэдвийн жагсаалт нь эргээд харж сонгогдсон: (в) бүлгийн 36 вирал сэдэв яг тэр үедээ (valid/test) оргилсон учраас "
     "жагсаалтад орсон (ADR 0005). Иймд үр дүнг бүлгээр гаргасан, гол дүгнэлт (а) дээр."),
    "Сэргээж тооцсон таамаг: тухайн өдөр хэрэглэгчид харагдсан тоо биш. Хадгалсан таамгийн log (ADR 0016)-той нэг тоо болгож холихгүй.",
    "data/aliases.csv нь одоогийн мэдлэг (нэр солигдсныг хожим мэдсэн байж болно).",
    "Түүхий өгөгдөл нь одоогийн data/processed: Wikimedia хожим засварласан бол тэр өдөр бэлэн байсантай зөрж болно (ховор).",
    ("Бодит Δ-ийн суурь нь тэр өдөр харагдсан as-of y_0 (evaluate.py-ийн test-д бүтэн өгөгдлөөр цэвэрлэсэн y_0) тул test-ийн "
     "нэг удаагийн тоотой шууд жишихгүй."),
    ("Өгөгдлийн сүүлийн ~14 өдрийн бодит утга түр зуурынх: бот-ын өсөлтийн шалгалт (төвлөрсөн 29 хоногийн медиан, t+1) "
     "бүрэн биш. Дахин ажиллуулахад шинэчлэгдэнэ."),
]


def _write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False, compression="zstd")
    tmp.replace(path)


def load_done(path: Path, model) -> pd.DataFrame | None:
    """Өмнө тооцсон таамгууд (бодит утгагүй). Өөр model хувилбарын мөр байвал ValueError: холихгүй."""
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    other = set(df["model_hash"].astype(str)) - {model.model_hash}
    if other:
        raise ValueError(f"{path}: өөр model хувилбарын мөр ({', '.join(sorted(train.short_version(h) for h in other))}), "
                         f"ачаалсан нь {train.short_version(model.model_hash)}. Хувилбарыг холихгүй.")
    return df.drop(columns=[c for c in df.columns if c.startswith("actual_")] + ["group"], errors="ignore")


def add_actuals(raw: live.RawCache, rows: pd.DataFrame) -> pd.DataFrame:
    """h бүрт бодит Δ, pct, уншилт (модулийн тайлбар). D + h нь өгөгдлөөс хойш бол NaN."""
    cl = pd.concat([c[["date", "article", "y", "views"]] for c in serve.clean_chunks(raw)], ignore_index=True)
    cl = cl.set_index([cl["article"].astype(str), "date"])
    out = rows.copy()
    for h in HORIZONS:
        idx = pd.MultiIndex.from_arrays([out["article"], out["asof"] + pd.Timedelta(days=h)])
        y = cl["y"].reindex(idx).to_numpy(dtype=float)
        p = scoring.pct(out["y_0"].to_numpy(), y)
        out[f"actual_delta_h{h}"] = y - out["y_0"].to_numpy()
        out[f"actual_pct_h{h}"] = np.where(np.isfinite(p), p, np.nan)
        out[f"actual_views_h{h}"] = cl["views"].reindex(idx).to_numpy(dtype=float)
    return out


def group_summary(d: pd.DataFrame, interval: dict) -> dict:
    """Нэг бүлгийн h бүрийн хэмжүүр, бодит утгатай мөрүүд дээр. MAE, skill (өдрөөр bootstrap), хамралт нь evaluate.py-ийн
    функцууд, гэхдээ бодит Δ-ийн суурь нь as-of y_0 (модулийн тайлбар) тул test-ийн нэг удаагийн тоотой шууд жишихгүй."""
    g = {"topics": int(d["article"].nunique()), "days": int(d["asof"].nunique())}
    for h in HORIZONS:
        k, ok = f"h{h}", d[f"actual_delta_h{h}"].notna()
        x = d[ok]
        delta, hat = x[f"actual_delta_h{h}"], x[f"delta_hat_h{h}"]
        if x.empty:
            g[k] = {"rows": 0}
            continue
        point, lo, hi = evaluate.skill_ci(pd.DataFrame({"date": x["asof"], "err_model": (hat - delta).abs(),
                                                        "err_naive": delta.abs()}))
        g[k] = {"rows": int(len(x)), "days": int(x["asof"].nunique()),
                "mae": {"model": round(float((hat - delta).abs().mean()), 5), "naive": round(float(delta.abs().mean()), 5)},
                "skill": {"point": round(point, 5), "lo": round(lo, 5), "hi": round(hi, 5)},
                "coverage": round(evaluate.interval_coverage(delta, hat, interval[k]["lo"], interval[k]["hi"]), 5)}
    return g


def summarize(out: pd.DataFrame, model) -> dict:
    return {
        "source": SOURCE, "model_hash": model.model_hash, "model_version": train.short_version(model.model_hash),
        "from": str(FROM.date()), "through": str(out["asof"].max().date()), "days": int(out["asof"].nunique()),
        "rows": int(len(out)),
        "boundary": "asof ≥ test-ийн эхний өдөр (ADR 0015, 1-р дүрэм). Model-ийг дахин сургавал хилийг src/backtest.py-д шинэчилнэ.",
        "actual": "Δ = y_{D+h} (одоогийн бүтэн өгөгдлөөр цэвэрлэсэн) − y_0 (as-of D, тэр өдөр харагдсан); pct = x_{D+h} / x_0 − 1",
        "main_group": scoring.GROUP_CURATED, "group_notes": evaluate.GROUP_NOTES,
        "groups": {k: group_summary(out[out["group"] == k], model.meta["interval"])
                   for k in evaluate.GROUPS if (out["group"] == k).any()},
        "caveats": CAVEATS,
    }


def run(raw: live.RawCache, model, out_dir: Path = OUT_DIR, through: pd.Timestamp | None = None, log=print) -> dict:
    """Хилээс through (анхдагч нь raw.end) хүртэлх, өмнө тооцоогүй asof бүрийг replay хийж (өдөр бүрийн дараа хадгална),
    дараа нь бүх мөрийн бодит утга ба тайланг дахин тооцно. Буцаах: path, model_version, computed (шинээр тооцсон өдөр), summary."""
    start = boundary(model)
    version = train.short_version(model.model_hash)
    path = Path(out_dir) / version / FILE
    done = load_done(path, model)
    have = set() if done is None else set(pd.to_datetime(done["asof"]))
    through = raw.end if through is None else min(pd.Timestamp(through), raw.end)
    days = [d for d in sorted(pd.to_datetime(raw.total["date"])) if start <= d <= through and d not in have]
    parts = [] if done is None else [done]
    t0 = time.monotonic()
    for i, d in enumerate(days, 1):
        parts.append(replay(raw, model, d).assign(model_hash=model.model_hash, model_version=version))
        _write(pd.concat(parts, ignore_index=True), path)   # тасарвал дараагийн ажиллагаа эндээс үргэлжилнэ
        left = (time.monotonic() - t0) / i * (len(days) - i)
        log(f"{d.date()} ({i}/{len(days)}, үлдсэн ~{left / 60:.0f} мин)")
    if not parts:
        raise ValueError(f"{start.date()} … {through.date()} хооронд asof алга")
    rows = pd.concat(parts, ignore_index=True).sort_values(["asof", "article"]).reset_index(drop=True)
    out = add_actuals(raw, rows)
    out["group"] = out["article"].map(train.load_groups())
    _write(out, path)
    summary = summarize(out, model)
    (path.parent / SUMMARY).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": path, "model_version": version, "computed": len(days), "summary": summary}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.backtest", description="Сэргээж тооцсон backtest (ADR 0015)")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="хилээс сүүлийн өдөр хүртэл as-of replay (тооцсон өдрийг алгасна)")
    r.add_argument("--out", type=Path, default=OUT_DIR)
    r.add_argument("--through", type=pd.Timestamp, default=None, help="сүүлийн asof (анхдагч: data/processed-ийн сүүлийн өдөр)")
    args = p.parse_args(argv)
    res = run(live.RawCache.load(ROOT / "data" / "processed"), train.load(), args.out, args.through,
              log=lambda m: print(m, flush=True))
    s = res["summary"]
    print(f"{res['path']}: model {res['model_version']}, {s['from']} … {s['through']} ({s['days']} өдөр), "
          f"шинээр {res['computed']}")
    for k, g in s["groups"].items():
        print(f"  ({k}) " + ", ".join(f"h{h} skill {g[f'h{h}']['skill']['point']:+.1%} хамралт {g[f'h{h}']['coverage']:.1%}"
                                      for h in HORIZONS if g[f"h{h}"].get("rows")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
