"""
Track record-ын файл (ADR 0020, 0021, #51): "ийм нөхцөлд өмнөх таамгууд хэр зөв байсан бэ?"

Хоёр эх сурвалжаас ТУСАД НЬ, model хувилбар бүрээр (нэг тоо болгож холихгүй, ADR 0015, 0016):
  - сэргээж тооцсон: data/backtest/<model хувилбар>/backtest.parquet (`python -m src.backtest run`)
  - хадгалсан: forecast-log branch-ийн forecasts/*.json (`--log-dir`-д checkout хийсэн хавтас), бодит үр дүн нь одоогийн
    data/processed-оос. was_missing боловч тэр өдрийн мөр хожим ирсэн таамгийг оноонд оруулахгүй (ADR 0016, 5-р зүйл).
Хүснэгт бүр src/situation.track_record (код, таамгийн зурвас, "үргэлжлэх/унтрах" бүрээр n ба бодит үр дүнгийн хувь).
Тестийн нэг удаагийн тооноос БИШ.

Ажиллуулах (backtest-ийн дараа; сервер app/data/track_record.json-ийг /api/track-record-оор өгнө):
    python -m src.track_record build
    git worktree add ../forecast-log origin/forecast-log && python -m src.track_record build --log-dir ../forecast-log
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src import backtest, live, serve, situation, train

ROOT = Path(__file__).resolve().parents[1]
OUT = serve.TRACK_FILE   # сервер (/api/track-record) уншдаг файл


def recomputed_rows(model, backtest_dir: Path = backtest.OUT_DIR) -> pd.DataFrame | None:
    """Ачаалсан model хувилбарын сэргээж тооцсон таамаг + бодит үр дүн. Backtest хийгээгүй бол None."""
    path = Path(backtest_dir) / train.short_version(model.model_hash) / backtest.FILE
    if not path.exists():
        return None
    d = pd.read_parquet(path)
    missing = set(backtest.SITUATION_COLS) - set(d.columns)
    if missing:
        raise ValueError(f"{path}: {sorted(missing)} багана алга (#51-ээс өмнөх backtest). Хавтсыг устгаад дахин ажиллуул.")
    return d[situation.COLS]


def stored_rows(log_dir: Path, raw: live.RawCache) -> tuple[pd.DataFrame, dict]:
    """forecasts/*.json-ийн сэдэв бүрийн мөр + бодит үр дүн (backtest.add_actuals: суурь нь хадгалсан y_0).
    Буцаах: (мөрүүд, model хувилбар бүрийн алгассан тоо {hash: {"late_data", "no_code"}})."""
    rows, no_code = [], {}
    for f in sorted((Path(log_dir) / "forecasts").glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        no_code.setdefault(rec["model_hash"], 0)
        for t in rec["topics"]:
            if t.get("h3") is None or t.get("y_0") is None:
                continue              # feature дутуу тул таамаглаагүй сэдэв
            if t.get("situation") is None:
                no_code[rec["model_hash"]] += 1   # #51-ээс өмнөх хэлбэрийн бичлэг: тэр өдөр харуулсан код мэдэгдэхгүй
                continue
            rows.append({"asof": pd.Timestamp(rec["asof"]), "article": t["article"], "model_hash": rec["model_hash"],
                         "was_missing": bool(t["was_missing"]), "measurable": bool(t["measurable"]), "y_0": float(t["y_0"]),
                         "pct_h3": np.nan if t["h3"]["pct"] is None else float(t["h3"]["pct"]),
                         "cycle": np.nan if t.get("cycle") is None else float(t["cycle"]),
                         "situation": t["situation"], "anomaly": bool(t.get("anomaly")), "verdict": t.get("verdict")})
    cols = situation.COLS + ["article"]
    skipped = lambda late: {h: {"late_data": int(late.get(h, 0)), "no_code": n} for h, n in no_code.items()}   # noqa: E731
    if not rows:
        return pd.DataFrame(columns=cols), skipped({})
    d = pd.DataFrame(rows)
    arrived = pd.MultiIndex.from_frame(raw.pageviews[["article", "date"]].astype({"article": str}))
    late = d["was_missing"].to_numpy() & pd.MultiIndex.from_arrays([d["article"], d["asof"]]).isin(arrived)
    late_by = d.loc[late, "model_hash"].value_counts().to_dict()
    d = backtest.add_actuals(raw, d[~late].reset_index(drop=True))
    d["group"] = d["article"].map(train.load_groups())
    d["verdict"] = d["verdict"].astype(object).where(d["verdict"].notna(), None)
    return d[cols], skipped(late_by)


def build(model, raw: live.RawCache, log_dir: Path | None = None, backtest_dir: Path = backtest.OUT_DIR) -> dict:
    """{"sources": [сэргээж тооцсон (ачаалсан model), хадгалсан (model хувилбар бүрээр, log-д гарсан дарааллаар)]}."""
    sources = []
    rec = recomputed_rows(model, backtest_dir)
    if rec is not None:
        sources.append(situation.track_record(rec, "recomputed"))
    if log_dir is not None:
        rows, skipped = stored_rows(log_dir, raw)
        for h in dict.fromkeys(rows["model_hash"]):
            sources.append({**situation.track_record(rows[rows["model_hash"] == h], "stored"), "skipped": skipped[h]})
    return {"sources": sources}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.track_record", description="Track record (ADR 0020, 0021)")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="app/data/track_record.json-ийг дахин бичнэ")
    b.add_argument("--log-dir", type=Path, default=None, help="forecast-log branch-ийн checkout (хадгалсан таамаг)")
    b.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args(argv)
    out = build(train.load(), live.RawCache.load(ROOT / "data" / "processed"), args.log_dir)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for s in out["sources"]:
        v = {e["key"]: e for e in s["by_verdict"]}
        print(f"{s['source']} {s['model_version']} {s['from']} … {s['through']} ({s['days']} өдөр): n {s['base']['n']}, "
              f"үргэлжлэх {v['continue']['n']} ({v['continue']['hit']} / ердийн үед {v['continue']['base_hit']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
