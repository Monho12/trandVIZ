"""
Хадгалсан таамгийн өдөр тутмын log (ADR 0016, #46). GitHub Actions өдөр бүр ажиллуулж `forecast-log` branch-д commit хийнэ.

Ажиллуулах (Action, `.github/workflows/forecast-log.yml`):
    python -m src.forecast_log run --log-dir log --render-url https://trandviz.onrender.com --golden success
    python -m src.forecast_log alert --log-dir log --out alert.md

Сервертэй ИЖИЛ код: татах ба "D бэлэн үү" нь `src/live.update_cache`, таамаг нь `src/serve` (Snapshot -> predict),
model нь `app/model/` (`src/train.load`). Энд шинэ дүрэм зохиохгүй, зөвхөн хадгална.

- asof D = ажиллаж буй UTC өдрийн өчигдөр. Өөр өдрийг хэзээ ч бичихгүй: хожим нөхөхгүй, сэргээж тооцсоноор дүүргэхгүй.
- Түүхий өгөгдөл = `main`-ийн `data/processed/` (суурь) + log-ын `deltas/*.csv` (суурийн сүүлийн өдрөөс хойшхи нь л).
  Дутуу өдрүүдийг л Wikimedia-аас татаж, шинэ мөрүүдийг delta болгон хадгална.

Log-ын хавтас (`forecast-log` branch-ийн үндэс):
    forecasts/YYYY-MM-DD.json   asof D-ийн хадгалсан таамаг (нэг удаа бичигдэнэ, хэзээ ч засахгүй)
    deltas/YYYY-MM-DD.csv       тэр ажиллагаа шинээр татсан түүхий мөрүүд (pageviews, alias, total), нэр = сүүлийн өдөр
    attempts.jsonl              оролдлого бүрийн цаг ба статус (Wikimedia-ийн гаргалтын цагийг хожим тохируулахад)
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from src import live, serve, train, wiki

ROOT = Path(__file__).resolve().parents[1]
APP_REQUIREMENTS = ROOT / "requirements-app.txt"

# Оролдлогын статус. not_published, error нь src/live.py-ийнхтэй ижил утгатай.
LOGGED, ALREADY_LOGGED, NOT_PUBLISHED, ERROR = "logged", "already_logged", live.NOT_PUBLISHED, live.ERROR
DELTA_COLS = ["table", "date", "article", "category", "old_title", "views"]   # total-ийн мөрөнд views = total_views


def _day(d: pd.Timestamp) -> str:
    return pd.Timestamp(d).strftime("%Y-%m-%d")


def _utc(t: pd.Timestamp) -> str:
    return pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(x) -> float | None:
    """JSON-д: NaN/inf (x_0 = 0 үед хувь тодорхойгүй) -> null."""
    return float(x) if x is not None and np.isfinite(x) else None


def lib_versions() -> dict:
    """Python + requirements-app.txt-ийн сангууд (Render-тэй ижил pin, ADR 0016)."""
    names = [line.split("==")[0].strip() for line in APP_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    return {"python": platform.python_version(), **{n: metadata.version(n) for n in names}}


def forecast_path(log_dir: Path, asof: pd.Timestamp) -> Path:
    return Path(log_dir) / "forecasts" / f"{_day(asof)}.json"


def load_raw(base: live.RawCache, log_dir: Path) -> live.RawCache:
    """Суурь (`main`-ийн data/processed) + log-ын бүх delta. Суурьтай давхцсан огнооны delta-г тоохгүй (ADR 0016, 3-р зүйл):
    суурийг хожим дахин татаж шинэчилбэл суурийнх нь давуу."""
    files = sorted((Path(log_dir) / "deltas").glob("*.csv"))
    if not files:
        return base
    d = pd.concat([pd.read_csv(f, dtype={"article": "str", "category": "str", "old_title": "str"},
                               keep_default_na=False, parse_dates=["date"]) for f in files], ignore_index=True)
    d = d[d["date"] > base.end]
    d["date"] = d["date"].astype(base.total["date"].dtype)
    part = {t: g for t, g in d.groupby("table")}
    empty = d.iloc[:0]
    pv = part.get("pageviews", empty)[["date", "article", "category", "views"]]
    al = part.get("alias", empty)[["date", "views", "old_title", "article"]]
    tot = part.get("total", empty)[["date", "views"]].rename(columns={"views": "total_views"})
    cat = lambda a, b, col: pd.concat([a, b], ignore_index=True).astype({col: "int64"})   # noqa: E731
    return live.RawCache(cat(base.pageviews, pv, "views"), cat(base.alias, al, "views"), cat(base.total, tot, "total_views"))


def save_delta(log_dir: Path, old: live.RawCache, new: live.RawCache) -> Path | None:
    """`new`-д `old`-оос хойш нэмэгдсэн түүхий мөрүүд (old.end-ээс хойшхи огноо) -> deltas/<new.end>.csv. Шинэ мөргүй бол None.
    Нэр нь delta-ийн сүүлийн өдөр: татах хугацаа бүр өмнөхийнхөө дараагийн өдрөөс эхэлдэг тул нэр давхцахгүй
    (06:41-д partial -> 09:41-д D гэсэн ч)."""
    after = lambda df: df[df["date"] > old.end]   # noqa: E731
    d = pd.concat([after(new.pageviews).assign(table="pageviews"), after(new.alias).assign(table="alias"),
                   after(new.total).rename(columns={"total_views": "views"}).assign(table="total")],
                  ignore_index=True).reindex(columns=DELTA_COLS)
    if d.empty:
        return None
    d["date"] = pd.to_datetime(d["date"]).dt.strftime("%Y-%m-%d")
    path = Path(log_dir) / "deltas" / f"{_day(new.end)}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"{path}: delta-г дахин бичихгүй")
    d.to_csv(path, index=False)
    return path


def topic_rows(cache: live.RawCache, pred: pd.DataFrame, asof: pd.Timestamp, horizons) -> list[dict]:
    """Сэдэв бүрт нэг мөр (cache-ийн бүх сэдэв). Feature дутуу тул таамаглаагүй сэдэвт h талбарууд null.
    was_missing: asof өдөр сэдвийн (үндсэн нэрийн) мөр API-аас ирээгүй. 0 уншилт уу, хоцорсон уу гэдгийг ялгах боломжгүй
    тул сургалттай адил 0 гэж тооцсон (ADR 0016, 5-р зүйл)."""
    pv = cache.pageviews
    arrived = set(pv.loc[pv["date"] == asof, "article"])
    cats = pv.drop_duplicates("article").set_index("article")["category"]
    by = {r.article: r for r in pred.itertuples()}
    out = []
    for a in sorted(cats.index):
        r = by.get(a)
        row = {"article": a, "category": cats[a], "was_missing": a not in arrived,
               "views": None if r is None else int(r.views), "y_0": None if r is None else _num(r.y_0),
               "measurable": None if r is None else bool(r.measurable), "arrow": None if r is None else r.arrow}
        for h in horizons:
            row[f"h{h}"] = None if r is None else {
                "delta_hat": _num(getattr(r, f"delta_hat_h{h}")), "pct": _num(getattr(r, f"pct_h{h}")),
                "lo": _num(getattr(r, f"lo_h{h}")), "hi": _num(getattr(r, f"hi_h{h}")),
                "y": _num(getattr(r, f"views_h{h}"))}
        out.append(row)
    return out


MISMATCH_LIST = 20   # зөрүүтэй сэдвийн жагсаалтыг log-д хэдийг хүртэл бичих вэ (тоо нь бүгдийг тоолно)


def compare(ours: dict, theirs: dict, was_missing: dict[str, bool]) -> dict:
    """Render-ийн /api/trending-ийг манай (ижил кодоор тооцсон) /api/trending-тэй харьцуулна (ADR 0016, 2-р зүйл).
    Хоёулаа Render-ийн хэлбэрт (pct 5%-д тайрсан, уншилт бүхэлчилсэн) тул сэдэв бүрийн h1–h3 `pct`, `y`-г шууд жишнэ.
    asof өөр бол харьцуулахгүй. Зөрүү нь код биш өгөгдлийнх (Render татах үед сэдвийн мөр хоцорсон) байж болно: was_missing."""
    if theirs.get("asof") != ours["asof"]:
        return {"status": "skipped", "reason": f"Render-ийн asof {theirs.get('asof')}, манайх {ours['asof']}"}
    mine = {i["article"]: i["forecast"] for i in ours["items"]}
    other = {i["article"]: i["forecast"] for i in theirs.get("items", [])}
    common = sorted(mine.keys() & other.keys())
    bad, max_pct, max_y = [], 0.0, 0
    for a in common:
        diffs = []
        for h, (f, g) in enumerate(zip(mine[a], other[a]), start=1):
            if (f["pct"], f["y"]) == (g.get("pct"), g.get("y")):
                continue
            if f["pct"] is not None and g.get("pct") is not None:
                max_pct = max(max_pct, round(abs(f["pct"] - g["pct"]), 4))
            if g.get("y") is not None:
                max_y = max(max_y, abs(f["y"] - g["y"]))
            diffs.append({"article": a, "h": h, "was_missing": bool(was_missing.get(a)),
                          "log": {"pct": f["pct"], "y": f["y"]}, "render": {"pct": g.get("pct"), "y": g.get("y")}})
        if diffs:
            bad.append(diffs)
    return {"status": "compared", "n_compared": len(common),
            "only_log": len(mine.keys() - other.keys()), "only_render": len(other.keys() - mine.keys()),
            "n_mismatch": len(bad), "n_mismatch_was_missing": sum(d[0]["was_missing"] for d in bad),
            "max_pct_diff": max_pct, "max_y_diff": max_y,
            "mismatched": [x for d in bad for x in d][:MISMATCH_LIST]}


def _render_block(render, ours: dict, asof: pd.Timestamp, was_missing: dict) -> dict:
    """Best-effort: Render унтсан, алдаа, asof өөр бол skipped + шалтгаан. Таамаг ямар ч үед хадгалагдана."""
    if render is None:
        return {"status": "skipped", "reason": "Render-ийн URL өгөөгүй"}
    try:
        theirs = render(asof)
    except Exception as e:   # унтсан (timeout), 5xx, JSON биш
        return {"status": "skipped", "reason": f"{type(e).__name__}: {e}"}
    return compare(ours, theirs, was_missing)


def run_day(log_dir: Path, base: live.RawCache, fetcher: live.Fetcher, model, now: pd.Timestamp,
            render=None, golden: str | None = None) -> dict:
    """Нэг оролдлого: asof = now-ийн UTC өдрийн өчигдөр. Буцаах: attempts.jsonl-д бичсэн мөр.
    render(asof) -> Render-ийн /api/trending JSON (алдаа бол exception), эсвэл None (харьцуулахгүй).
    golden: Action дотор ажилласан tests/test_golden.py-ийн үр дүн ("success"/"failure"), бичихэд л хэрэглэнэ."""
    log_dir, now = Path(log_dir), pd.Timestamp(now)
    asof = now.normalize() - pd.Timedelta(days=1)
    attempt = {"run_at": _utc(now), "asof": _day(asof), "golden_test": golden,
               "model_version": train.short_version(model.model_hash)}

    def done(status: str, **extra) -> dict:
        attempt.update(status=status, **extra)
        _append(log_dir, attempt)
        return attempt

    if forecast_path(log_dir, asof).exists():
        return done(ALREADY_LOGGED)
    try:
        return _compute(log_dir, base, fetcher, model, now, asof, render, golden, done)
    except Exception as e:   # код/өгөгдлийн алдаа: оролдлогыг бичээд workflow-д дамжуулна (issue нээгдэнэ)
        done(ERROR, message=f"унасан: {type(e).__name__}: {e}")
        raise


def _compute(log_dir: Path, base, fetcher, model, now: pd.Timestamp, asof: pd.Timestamp, render, golden, done) -> dict:
    """run_day-ийн их бие: татах -> D бэлэн үү -> таамаг -> Render -> бичих. Буцаахдаа done(статус, ...)-аар л."""
    raw = load_raw(base, log_dir)
    res = live.update_cache(raw, fetcher, now.normalize())
    cache = res.cache
    new_days = sorted({_day(d) for d in cache.total["date"] if d > raw.end})
    save_delta(log_dir, raw, cache)   # D бэлэн биш ч өмнөх дутуу өдрүүд нэмэгдсэн байж болно (PARTIAL)
    info = {"wikimedia": res.status, "message": res.message, "fetched_days": new_days}
    if res.status == live.ERROR:
        return done(ERROR, **info)
    if cache.end != asof:      # D бэлэн биш (сервертэй ижил дүрэм: total_views ба сэдвүүдийн мөр, src/live.py)
        return done(NOT_PUBLISHED if cache.end < asof else ERROR,
                    **{**info, "message": res.message or f"cache {_day(cache.end)} хүртэл, asof {_day(asof)}"})

    snap = serve.Snapshot.from_raw(cache)
    pred = serve.predict(model, snap.universe)
    topics = topic_rows(cache, pred, asof, model.meta["horizons"])
    ours = json.loads(json.dumps(serve.trending(model, snap, now.normalize())))   # Render-ийн хэлбэр
    cmp = _render_block(render, ours, asof, {t["article"]: t["was_missing"] for t in topics})
    record = {
        "asof": _day(asof), "run_at": _utc(now),
        "model_hash": model.model_hash, "model_version": train.short_version(model.model_hash),
        "libs": lib_versions(), "golden_test": golden,
        "data": {"total_views": int(cache.total.loc[cache.total["date"] == asof, "total_views"].iloc[0]),
                 "topics": len(topics), "was_missing": sum(t["was_missing"] for t in topics),
                 "fetched_days": new_days},
        "render": cmp,
        "topics": topics,
    }
    path = forecast_path(log_dir, asof)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return done(LOGGED, **info, render={k: cmp.get(k) for k in ("status", "reason", "n_mismatch") if k in cmp})


def _append(log_dir: Path, attempt: dict) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / "attempts.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(attempt, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- цоорхой

LAST_ATTEMPT = pd.Timedelta(hours=9, minutes=41)   # D+1-ний сүүлийн cron (09:41 UTC): үүний дараа D-г нөхөх боломжгүй
ALERT_GAP_DAYS = 2                                 # дараалсан ийм олон цоорхой өдөр бол GitHub issue


def read_attempts(log_dir: Path) -> list[dict]:
    f = Path(log_dir) / "attempts.jsonl"
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def gap_alert(log_dir: Path, now: pd.Timestamp) -> str | None:
    """Сүүлийн ALERT_GAP_DAYS өдөр (өчигдрөөр дуусах) бүгд **цоорхой** бол issue-ийн текст, үгүй бол None.
    Цоорхой = хадгалсан таамаггүй, сүүлийн оролдлогын (D+1 09:41 UTC) цаг өнгөрсөн өдөр. Log эхлэхээс (анхны оролдлогын asof)
    өмнөх өдрийг тоохгүй. Workflow огт ажиллаагүй өдрүүд (GitHub унтраасан) дараагийн ажиллагаан дээр илэрнэ."""
    log_dir, now = Path(log_dir), pd.Timestamp(now)
    tried = read_attempts(log_dir)
    if not tried:
        return None
    start = min(pd.Timestamp(a["asof"]) for a in tried)
    days = [now.normalize() - pd.Timedelta(days=k) for k in range(ALERT_GAP_DAYS, 0, -1)]
    closed = lambda d: now >= d + pd.Timedelta(days=1) + LAST_ATTEMPT   # noqa: E731
    if not all(d >= start and closed(d) and not forecast_path(log_dir, d).exists() for d in days):
        return None
    lines = [f"Хадгалсан таамгийн log {ALERT_GAP_DAYS} өдөр дараалан цоорхой (ADR 0016): "
             f"{', '.join(_day(d) for d in days)} өдрийн таамаг бичигдээгүй, дахин нөхөхгүй.", "",
             "| asof | оролдлого | статус | тайлбар |", "|---|---|---|---|"]
    for a in tried:
        if a["asof"] in {_day(d) for d in days}:
            lines.append(f"| {a['asof']} | {a.get('run_at', '')} | {a.get('status', '')} | {a.get('message', '')} |")
    lines += ["", "Шалгах: Wikimedia-ийн гаргалт хоцорсон уу (`not_published`), Wikimedia унасан уу (`error`), "
              "эсвэл workflow-ийн log (Actions таб)."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- Render, CLI

RENDER_TIMEOUT = 150   # сек: Render free 15 минут хүсэлтгүй бол унтдаг, сэрэх нь ~1 минут (ADR 0011)
RENDER_WAIT = 300      # сек: сэрсэн Render эхлээд image-ийн хуучин өгөгдөлтэй, Wikimedia-аас ~3 минут татна (src/live.py)


def render_client(url: str, timeout: float = RENDER_TIMEOUT, wait: float = RENDER_WAIT, sleep=time.sleep):
    """run_day-ийн render(asof): /api/trending. asof нь хуучин бол (дөнгөж сэрсэн) нэг удаа хүлээгээд дахин асууна."""
    def fetch(asof: pd.Timestamp) -> dict:
        for i in range(2):
            r = requests.get(f"{url.rstrip('/')}/api/trending", timeout=timeout, headers={"User-Agent": wiki.USER_AGENT})
            r.raise_for_status()
            data = r.json()
            if i == 1 or str(data.get("asof", "")) >= _day(asof):
                break
            sleep(wait)
        return data
    return fetch


LOG_README = """# forecast-log

Хадгалсан таамгийн өдөр тутмын log (ADR 0016). `.github/workflows/forecast-log.yml` (main) өдөр бүр 06:41, 09:41 UTC-д бичнэ.
Энэ branch-ийг гараар бүү засаарай: зөвхөн нэмэгддэг, `main`-д merge хийхгүй.

- `forecasts/YYYY-MM-DD.json`: asof өдрийн хадгалсан таамаг (model хувилбар, сэдэв бүрийн h1–h3 Δ̂/pct/80% интервал/уншилт,
  `was_missing`, сангийн хувилбар, Render-тэй харьцуулалт). Нэг удаа бичигдэнэ.
- `deltas/YYYY-MM-DD.csv`: тэр ажиллагаа Wikimedia-аас шинээр татсан түүхий мөрүүд (нэр = delta-ийн сүүлийн өдөр). Дараагийн ажиллагаа
  `main`-ийн `data/processed/` + эдгээрээс эхэлнэ.
- `attempts.jsonl`: оролдлого бүрийн цаг ба статус (`logged`, `already_logged`, `not_published`, `error`).
"""


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None).floor("s")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.forecast_log", description="Хадгалсан таамгийн log (ADR 0016)")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="өчигдрийн таамгийг тооцож log-д бичнэ")
    r.add_argument("--log-dir", type=Path, required=True)
    r.add_argument("--render-url", default=None)
    r.add_argument("--golden", default=None, help="tests/test_golden.py-ийн үр дүн (steps.<id>.outcome)")
    a = sub.add_parser("alert", help="2 өдөр дараалан цоорхой бол issue-ийн текстийг --out-д бичнэ")
    a.add_argument("--log-dir", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)

    if args.cmd == "alert":
        body = gap_alert(args.log_dir, utc_now())
        args.out.write_text(body or "", encoding="utf-8")
        print("цоорхой: issue нээнэ" if body else "цоорхой алга")
        return 0

    args.log_dir.mkdir(parents=True, exist_ok=True)
    if not (args.log_dir / "README.md").exists():
        (args.log_dir / "README.md").write_text(LOG_README, encoding="utf-8")
    att = run_day(args.log_dir, live.RawCache.load(ROOT / "data" / "processed"), live.WikiFetcher(), train.load(),
                  utc_now(), render=render_client(args.render_url) if args.render_url else None, golden=args.golden)
    render = att.get("render", {})
    extra = f", Render {render.get('status')}" + (f" ({render['n_mismatch']} зөрүүтэй)" if "n_mismatch" in render else "")
    print(f"asof {att['asof']}: {att['status']}" + (extra if render else "")
          + (f" - {att['message']}" if att.get("message") and att["status"] != LOGGED else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
