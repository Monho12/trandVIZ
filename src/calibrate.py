"""
Калибровк: 🔥 босго T ба 80% интервалыг (в)-гүй valid-аас сонгож, app/model/meta.json-д нэмнэ (issue #6).

  - T (ADR 0004): хэмжигдэх сэдвийн таамагласан pct(h3) дээр, T = max(өдөрт ~7.5 🔥 гаргах босго, 25%).
  - 80% интервал (ADR 0003): residual Δ − Δ̂-ийн 10% ба 90%-ийн квантил h бүрт, (в)-гүй valid-ийн БҮХ мөр дээр
    (алгоритм сонголттой яг ижил мөрүүд; T нь эдгээрийн хэмжигдэх хэсэг. Майк зөвшөөрсөн (Claude санал болгосон), 2026-11-10).
Test-ийг энд ОГТ уншихгүй. Model-ийг дахин сургахгүй: app/model/-д экспортлосон ялагчийг ачаална.

Ажиллуулах:  python -m src.calibrate  ->  app/model/meta.json ("fire", "interval" талбар)
`python -m src.train` meta.json-ийг шинээр бичдэг тул дахин сургасны дараа ҮҮНИЙГ дахин ажиллуулна.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import scoring, train
from src.features import HORIZONS

P = train.P
MODEL_DIR = train.MODEL_DIR
PCT_QUANTILES = (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)


def valid_frame(model: train.LoadedModel) -> pd.DataFrame:
    """(в)-гүй valid мөрүүд + measurable + h бүрийн Δ, Δ̂ ба h3-ын таамагласан pct (`pred_pct`)."""
    feats = pd.read_parquet(P / "features.parquet")
    feats = feats[feats["split"] == "valid"]
    va = feats[train.row_sets(feats, train.load_groups())["valid"]].copy()

    # Хэмжигдэх эсэх: дутуугүй өдөр тутмын цувралаас (features.parquet-д purge-ийн цоорхой бий)
    cl = pd.read_parquet(P / "clean.parquet", columns=["date", "article", "y"])
    cl["measurable"] = scoring.is_measurable(cl)
    va = va.merge(cl[["article", "date", "measurable"]], on=["article", "date"], how="left")

    for h in HORIZONS:
        va[f"delta_h{h}"] = va[f"y_h{h}"] - va["y_0"]
        va[f"delta_hat_h{h}"] = model.predict(va, h)
    va["pred_pct"] = scoring.predicted_pct(va["y_0"], va["delta_hat_h3"])
    return va


def calibrate(va: pd.DataFrame) -> dict:
    """valid_frame-ийн хүснэгтээс meta.json-д нэмэх "fire", "interval" талбарууд."""
    meas = va[va["measurable"].fillna(False).astype(bool)]
    tuned = scoring.tuned_threshold(va)
    T = scoring.fire_threshold(tuned)
    fire = {
        "T": round(T, 4),
        "T_tuned": round(tuned, 4),
        "rule": f"T = max(өдөрт ~{scoring.FIRES_PER_DAY_TARGET:g} 🔥 гаргах босго (T_tuned), {scoring.T_FLOOR:.0%}), "
                "(в)-гүй valid, хэмжигдэх сэдэв, таамагласан pct(h3) (ADR 0004)",
        "target_per_day": scoring.FIRES_PER_DAY_TARGET,
        "per_day_at_T": round(scoring.fires_per_day(va, T), 2),
        "per_day_at_25pct": round(scoring.fires_per_day(va, scoring.T_FLOOR), 2),
        "valid_days": int(va["date"].nunique()),
        "measurable_rows": int(len(meas)),
        "pred_pct_quantiles": {f"{q:.2f}": round(float(v), 4) for q, v in meas["pred_pct"].quantile(PCT_QUANTILES).items()},
    }
    interval = {
        "q": list(scoring.INTERVAL_Q),
        "rule": f"Δ̂ + [lo, hi]: residual Δ − Δ̂-ийн {scoring.INTERVAL_Q[0]:.0%}/{scoring.INTERVAL_Q[1]:.0%} квантил, "
                "(в)-гүй valid-ийн бүх мөр; pct руу expm1-ээр (ADR 0003)",
    }
    for h in HORIZONS:
        lo, hi = scoring.residual_quantiles(va[f"delta_h{h}"], va[f"delta_hat_h{h}"])
        interval[f"h{h}"] = {"lo": round(lo, 5), "hi": round(hi, 5)}
    return {"fire": fire, "interval": interval}


def run(model_dir: Path = MODEL_DIR, log=print) -> dict:
    """Ялагч model-ийг ачаалж, калибровк хийж, meta.json-д бичнэ. Буцаах: {"valid": va, **calibrate(va)}."""
    model = train.load(model_dir)
    va = valid_frame(model)
    cal = calibrate(va)
    meta = {**model.meta, **cal}
    (Path(model_dir) / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    f, iv = cal["fire"], cal["interval"]
    log(f"T = {f['T']:.0%} (тааруулсан {f['T_tuned']:+.1%}): өдөрт {f['per_day_at_T']} 🔥 "
        f"(T = 25% үед {f['per_day_at_25pct']}), {f['valid_days']} өдөр")
    for h in HORIZONS:
        log(f"h{h}: 80% интервал Δ̂ + [{iv[f'h{h}']['lo']:+.4f}, {iv[f'h{h}']['hi']:+.4f}]")
    return {"valid": va, **cal}


if __name__ == "__main__":
    run()
