"""Track record-ын файл (ADR 0020, #51): сэргээж тооцсон (backtest.parquet) ба хадгалсан (forecast-log) таамгаас тусад нь,
model хувилбар бүрээр.  pytest -q"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import backtest, live, scoring, track_record, train  # noqa: E402

D = pd.Timestamp("2026-06-15")
SAMPLE = ["Donald_Trump", "Joe_Biden", "Taylor_Swift"]


@pytest.fixture(scope="module")
def raw() -> live.RawCache:
    return live.RawCache.load(ROOT / "data" / "processed")


@pytest.fixture(scope="module")
def model():
    return train.load()


def stored_record(raw, model, asof, topics: dict) -> dict:
    """Хадгалсан log-ын бичлэг (src/forecast_log.py-ийн хэлбэр), зөвхөн track record-д хэрэгтэй талбартай."""
    rows = []
    for a, kw in topics.items():
        rows.append({"article": a, "was_missing": False, "measurable": True, "y_0": 1.0, "anomaly": False, "z": 0.0,
                     "cycle": 0.0, "situation": "rebound", "verdict": None,
                     "h3": {"pct": 0.2, "delta_hat": 0.1, "lo": 0.0, "hi": 0.3, "y": 10.0}, **kw})
    return {"asof": str(asof.date()), "model_hash": model.model_hash, "model_version": train.short_version(model.model_hash),
            "topics": rows}


def write_log(tmp: Path, records: list[dict]) -> Path:
    (tmp / "forecasts").mkdir(parents=True)
    for r in records:
        (tmp / "forecasts" / f"{r['asof']}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    return tmp


def test_stored_rows_score_the_logged_forecast_against_actual_h3_and_drop_late_data(tmp_path, raw, model):
    """Бодит pct (h3) нь хадгалсан y_0-оос (тэр өдөр харагдсан) одоогийн өгөгдлийн D+3 хүртэл. was_missing боловч тэр
    сэдвийн D өдрийн мөр хожим ирсэн бол "өгөгдөл хоцорсон": оноонд орохгүй (ADR 0016, 5-р зүйл). Код/дүгнэлтгүй (хуучин
    хэлбэрийн) бичлэгийг тоолж алгасна."""
    log = write_log(tmp_path, [stored_record(raw, model, D, {
        "Donald_Trump": {"y_0": 2.0}, "Joe_Biden": {"was_missing": True}, "Taylor_Swift": {"situation": None}})])
    rows, skipped = track_record.stored_rows(log, raw)
    assert list(rows["article"]) == ["Donald_Trump"] and skipped == {model.model_hash: {"late_data": 1, "no_code": 1}}
    cl = backtest.add_actuals(raw, pd.DataFrame({"asof": [D], "article": ["Donald_Trump"], "y_0": [2.0]}))
    assert rows["actual_pct_h3"].iloc[0] == pytest.approx(cl["actual_pct_h3"].iloc[0])
    assert rows["actual_pct_h3"].iloc[0] == pytest.approx(scoring.pct(2.0, cl["actual_delta_h3"].iloc[0] + 2.0))
    assert rows["group"].iloc[0] == "а" and rows["pct_h3"].iloc[0] == 0.2 and rows["situation"].iloc[0] == "rebound"


def test_build_keeps_recomputed_and_stored_apart_each_with_its_model_version(tmp_path, raw, model):
    small = live.RawCache(*(df[df["article"].isin(SAMPLE)].reset_index(drop=True) if "article" in df else df
                            for df in (raw.pageviews, raw.alias, raw.total)))
    bt = tmp_path / "bt"
    backtest.run(backtest.truncate(small, backtest.FROM + pd.Timedelta(days=5)), model, bt)
    other = stored_record(raw, model, D, {"Donald_Trump": {}})
    other["model_hash"] = "f" * 64
    log = write_log(tmp_path / "log", [stored_record(raw, model, D, {"Donald_Trump": {}}),
                                       {**other, "asof": "2026-06-16"}])
    out = track_record.build(model, raw, log_dir=log, backtest_dir=bt)
    keys = [(s["source_key"], s["model_version"]) for s in out["sources"]]
    v = train.short_version(model.model_hash)
    assert keys == [("recomputed", v), ("stored", v), ("stored", "vfffffff")]
    rec = out["sources"][0]
    assert rec["from"] == "2026-04-01" and rec["base"]["n"] == 3 * 3   # (а) 3 сэдэв × бодит h3-тай 3 өдөр
    assert out["sources"][1]["skipped"] == {"late_data": 0, "no_code": 0}


def test_skipped_counts_belong_to_their_own_model_version(tmp_path, raw, model):
    mine = stored_record(raw, model, D, {"Donald_Trump": {}, "Joe_Biden": {"was_missing": True}})
    other = stored_record(raw, model, pd.Timestamp("2026-06-16"), {"Donald_Trump": {}, "Taylor_Swift": {"situation": None}})
    other["model_hash"] = "f" * 64
    out = track_record.build(model, raw, log_dir=write_log(tmp_path, [mine, other]), backtest_dir=tmp_path / "none")
    skipped = {s["model_version"]: s["skipped"] for s in out["sources"]}
    assert skipped == {train.short_version(model.model_hash): {"late_data": 1, "no_code": 0},
                       "vfffffff": {"late_data": 0, "no_code": 1}}


def test_build_without_a_log_has_only_the_recomputed_source(tmp_path, raw, model):
    small = live.RawCache(raw.pageviews[raw.pageviews["article"] == "Donald_Trump"].reset_index(drop=True),
                          raw.alias.iloc[:0], raw.total)
    backtest.run(backtest.truncate(small, backtest.FROM + pd.Timedelta(days=3)), model, tmp_path)
    out = track_record.build(model, raw, log_dir=None, backtest_dir=tmp_path)
    assert [s["source_key"] for s in out["sources"]] == ["recomputed"]
