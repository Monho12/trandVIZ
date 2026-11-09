"""
Baseline-ууд: LightGBM-ийг юутай харьцуулах вэ?

Model "ухаантай" гэдгийг батлахын тулд энгийн аргуудаас БАГА алдаатай байх ёстой.

  naive    : ŷ(t+h) = y(t)        -> "маргааш өнөөдрийнх шиг"
  seasonal : ŷ(t+h) = y(t+h-7)    -> "зорилтот өдөр 7 хоногийн өмнөх ижил гарагийнх шиг"
             (t+h-7 <= t тул зөвхөн өнгөрсөн мэдээлэл, leakage-гүй)

Алдаа: MAE, log1p(анхаарал) хуваарьт. Horizon бүр (1, 2, 3), valid ба test дээр.
Ажиллуулах: python -m src.baselines
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.features import HORIZONS

P = Path(__file__).resolve().parents[1] / "data" / "processed"


def seasonal_pred(feats: pd.DataFrame, clean: pd.DataFrame, h: int) -> pd.Series:
    """Мөр бүрт y(t+h-7)-г clean хүснэгтээс огноогоор нь хайж олно (дутуу бол NaN)."""
    look = clean[["article", "date", "y"]].copy()
    look["date"] = look["date"] - pd.Timedelta(days=h - 7)   # t+h-7 өдрийг t болгож шилжүүлнэ
    out = feats[["article", "date"]].merge(look, on=["article", "date"], how="left")
    return pd.Series(out["y"].to_numpy(), index=feats.index)


def compute(feats: pd.DataFrame, clean: pd.DataFrame) -> dict:
    res = {}
    for split in ("valid", "test"):
        d = feats[feats["split"] == split]
        res[split] = {}
        for h in HORIZONS:
            y = d[f"y_h{h}"]
            s = seasonal_pred(d, clean, h)
            ok = s.notna()
            res[split][f"h{h}"] = {
                "naive": round(float(np.mean(np.abs(y - d["y_0"]))), 4),
                "seasonal": round(float(np.mean(np.abs(y[ok] - s[ok]))), 4),
                "rows": int(len(d)),
            }
    return res


def main() -> dict:
    from src import clean as clean_mod
    cl = pd.read_parquet(P / "clean.parquet") if (P / "clean.parquet").exists() else clean_mod.build()
    feats = pd.read_parquet(P / "features.parquet", columns=["date", "article", "split", "y_0", "y_h1", "y_h2", "y_h3"])
    res = compute(feats, cl)
    (P / "baselines.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    for split, hs in res.items():
        for h, v in hs.items():
            print(f"{split:5s} {h}: naive {v['naive']:.4f}   seasonal {v['seasonal']:.4f}")
    return res


if __name__ == "__main__":
    main()
