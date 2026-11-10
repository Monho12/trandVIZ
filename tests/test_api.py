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


def test_map_categories_insights(client):
    mp = client.get("/api/map").json()
    assert len(mp["items"]) == 40 and mp["total_topics"] == 301
    cs = client.get("/api/categories").json()["categories"]
    assert "Бусад" in {c["key"] for c in cs} and all(len(c["topics"]) <= 4 for c in cs)
    assert client.get("/api/insights").json()["decay"]
