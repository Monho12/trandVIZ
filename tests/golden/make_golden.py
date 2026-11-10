"""API-ийн "golden" хариуг бичнэ: санах ойн оновчлол (ADR 0012) /api/*-ийн хариуг ЯГ хэвээр үлдээж буйг
tests/test_golden.py шалгадаг. Model, data/processed эсвэл scoring-ийг ЗОРИУДААР өөрчилбөл дахин үүсгэнэ:

    python tests/golden/make_golden.py            # api_sha256.json-ийг шинэчилнэ
    python tests/golden/make_golden.py --dump     # + бүтэн JSON-ийг tests/golden/_dump/-д (зөрүү хайхад, git-д орохгүй)

Өгөгдөл: image-ийн data/processed (data/live биш), Wikimedia-гүй, "өнөөдөр" = TODAY (asof-ийн хоцрогдол тогтмол)."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
GOLDEN = HERE / "api_sha256.json"
TODAY = "2026-11-10"
ENDPOINTS = {"trending": "/api/trending", "topic_ChatGPT": "/api/topic/ChatGPT", "map": "/api/map",
             "categories": "/api/categories", "model": "/api/model"}
VOLATILE = {"loaded_at", "snapshot_built_at", "refresh"}   # /api/model["live"]: процесс эхэлсэн цаг


def responses() -> dict:
    """data/processed дээрх серверийн хариу (refresh-гүй, TODAY-аар)."""
    os.environ["SHUUGIAN_REFRESH"] = "0"
    import pandas as pd
    from fastapi.testclient import TestClient

    import app.main as m
    m.LIVE_DIR = HERE / "_no_live"                        # Майкийн data/live/-ийг бүү уншаарай
    today = pd.Timestamp(TODAY)
    orig, m.local_today = m.local_today, lambda: today
    try:
        with TestClient(m.app) as c:
            out = {k: c.get(ep).json() for k, ep in ENDPOINTS.items()}
    finally:
        m.local_today = orig
    out["model"]["live"] = {k: v for k, v in out["model"]["live"].items() if k not in VOLATILE}
    return out


def canonical(v) -> str:
    return json.dumps(v, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def digests(res: dict) -> dict:
    return {k: hashlib.sha256(canonical(v).encode("utf-8")).hexdigest() for k, v in res.items()}


def main() -> None:
    res = responses()
    if "--dump" in sys.argv:
        (HERE / "_dump").mkdir(exist_ok=True)
        for k, v in res.items():
            (HERE / "_dump" / f"{k}.json").write_text(canonical(v), encoding="utf-8")
    GOLDEN.write_text(json.dumps({"today": TODAY, "sha256": digests(res)}, indent=1) + "\n", encoding="utf-8")
    print(GOLDEN.read_text())


if __name__ == "__main__":
    main()
