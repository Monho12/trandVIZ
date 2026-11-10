"""app/main.py: model сайтын ард (ADR 0008). Image-ийн data/processed + app/model дээр, Wikimedia-гүй.  pytest -q"""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SHUUGIAN_REFRESH"] = "0"
fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with fastapi_testclient.TestClient(app) as c:
        yield c


def test_trending_top10_is_ten_measurable_topics_ranked_by_predicted_pct(client):
    d = client.get("/api/trending").json()
    assert d["mock"] is False
    top = d["items"][:10]
    assert [t["rank"] for t in top] == list(range(1, 11))
    assert all(t["measurable"] for t in top)
    assert [t["pct"] for t in top] == sorted((t["pct"] for t in top), reverse=True)
    assert all(t["rank"] is None for t in d["items"][10:])
    # 🔥 зөвхөн хэмжигдэх сэдэв ба pct ≥ T
    assert all(t["measurable"] and t["pct"] >= d["T"] - 0.025 for t in d["items"] if t["fire"])


def test_forecast_has_concrete_dates_interval_and_no_viral_category(client):
    d = client.get("/api/trending").json()
    t = d["items"][0]
    assert [f["d"] for f in t["forecast"]] == [str(x.date()) for x in pd.date_range(d["asof"], periods=4)[1:]]
    assert t["dates"] == d["dates"] and "–" in d["dates"]
    for x in d["items"]:
        assert all(f["lo"] <= f["y"] <= f["hi"] for f in x["forecast"])
        if x["pct"] is None:   # өнөөдөр 0 уншилт: хувь тодорхойгүй
            continue
        assert x["interval"]["lo"] <= x["pct"] <= x["interval"]["hi"]
        assert x["interval"]["lo"] >= -1.0
        assert all(f["lo"] <= f["y"] <= f["hi"] for f in x["forecast"])
    assert "viral" not in {x["category"] for x in d["items"]}


def test_topic_runs_model_and_unknown_topic_is_404(client):
    t = client.get("/api/topic/ChatGPT").json()
    assert t["article"] == "ChatGPT" and len(t["history"]) == 180 and len(t["forecast"]) == 3
    assert t["label"] and t["interval_text"].startswith("80%")
    assert client.get("/api/topic/Not_a_topic_we_track").status_code == 404


def test_model_endpoint_shows_loaded_model_and_data_asof(client):
    m = client.get("/api/model").json()
    live = m["live"]
    assert live["algo"] == "catboost" and live["trained_at"].startswith("2026-11-09")
    assert live["data_asof"] == m["asof"]
    assert m["winner"] == "catboost" and m["metrics"] and m["test_end"]
    # "Яаж хийсэн бэ?": бүх тоо meta.json / өгөгдлөөс
    p = m["pipeline"]
    assert p["topics"] == 301 and p["n_features"] == 18 and p["purge_days"] == 3 and p["trials"] == 225
    assert p["algo_name"] == "CatBoost" and p["clean_rows"] > 0 and p["naive_h3"]["valid"] < p["naive_h3"]["train"]
    assert m["names"]["naive"] == "Одоогийнхтой адилхан" and set(m["valid"]["mean"]) == {"lightgbm", "xgboost", "catboost", "naive"}


def test_map_categories_insights(client):
    mp = client.get("/api/map").json()
    assert len(mp["items"]) == 40 and mp["total_topics"] == 301
    cs = client.get("/api/categories").json()["categories"]
    assert "Бусад" in {c["key"] for c in cs} and all(len(c["topics"]) <= 4 for c in cs)
    assert client.get("/api/insights").json()["decay"]

def test_topic_with_zero_views_today_has_no_pct_and_serializes_to_json():
    """x_0 = 0 бол pct = x̂ / 0 тодорхойгүй: inf JSON-д алдаа өгдөг байсан (WWE_Bash_in_Berlin, 2026-11-09)."""
    import json
    import numpy as np
    from types import SimpleNamespace
    from src import serve

    meta = {"features": ["f"], "horizons": [1, 2, 3], "fire": {"T": 0.25},
            "interval": {f"h{h}": {"lo": -0.1, "hi": 0.2} for h in (1, 2, 3)}}
    model = SimpleNamespace(meta=meta, predict=lambda r, h: np.full(len(r), 0.3))
    rows = pd.DataFrame({"article": ["Zero", "Some"], "category": ["sports", "sports"], "f": [1.0, 1.0],
                         "y_0": [0.0, np.log1p(5.0)], "total_views": [3e8, 3e8], "measurable": [False, True],
                         "views": [0, 15], "normal": [3.0, 12.0]})
    p = serve.predict(model, rows)
    z = next(r for r in p.itertuples() if r.article == "Zero")
    hist = pd.DataFrame({"date": [pd.Timestamp("2026-11-09")], "views": [0]})
    it = serve.item(z, hist, pd.Timestamp("2026-11-09"))
    json.dumps(it, allow_nan=False)
    assert it["pct"] is None and it["label"] == "" and it["interval_text"] == "" and it["arrow"] is None
    assert it["forecast"][2]["y"] >= 0 and it["forecast"][2]["pct"] is None
    s = next(r for r in p.itertuples() if r.article == "Some")
    assert serve.item(s, hist, pd.Timestamp("2026-11-09"))["pct"] is not None
