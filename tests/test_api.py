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
    # 🔥 зөвхөн хэмжигдэх сэдэв ба pct ≥ T (харагдах pct нь тэг рүү тайрсан тул мөн ≥ T)
    assert all(t["measurable"] and t["pct"] >= d["T"] for t in d["items"] if t["fire"])


def test_home_chip_label_agrees_with_arrow_and_fires_count(client):
    """Нүүрний чип API-ийн label-ийг харуулна (#31): шошго сумаараа эхэлнэ, тайлбарын 🔥-ийн тоо чиптэй таарна."""
    d = client.get("/api/trending").json()
    for t in d["items"]:
        if t["pct"] is not None:
            assert t["label"].startswith(t["arrow"]), (t["article"], t["arrow"], t["label"])
            assert t["label"].startswith("🔥") == t["fire"]
    assert d["fires"] == sum(t["fire"] for t in d["items"][:d["top_n"]])


def _check_forecast(d):
    t = d["items"][0]
    assert [f["d"] for f in t["forecast"]] == [str(x.date()) for x in pd.date_range(d["asof"], periods=4)[1:]]
    assert t["dates"] == d["dates"] and "–" in d["dates"]
    for x in d["items"]:
        if x["pct"] is None:  # asof өдөр 0 уншилт (x_0 = 0, PR #21): хувь хэмжигдэхгүй
            assert x["interval"]["lo"] is None and x["interval"]["hi"] is None
            assert x["rank"] is None and x["fire"] is False
            continue
        assert x["interval"]["lo"] <= x["pct"] <= x["interval"]["hi"]
        assert x["interval"]["lo"] >= -1.0
        assert all(f["lo"] <= f["y"] <= f["hi"] for f in x["forecast"])
    assert "viral" not in {x["category"] for x in d["items"]}


def test_forecast_has_concrete_dates_interval_and_no_viral_category(client):
    _check_forecast(client.get("/api/trending").json())


def test_forecast_check_holds_when_some_topics_have_zero_views_on_asof(client, monkeypatch):
    """Майкийн data/live/ cache-д 11/09-нд WWE_Bash_in_Berlin = 0 уншилт байсан (PR #21: pct/interval = null).
    data/live/-гүй орчинд ч энэ тохиолдлыг давтахын тулд хэдэн сэдвийн x_0-г 0 болгоно."""
    from app.main import state
    rows = state.snapshot.universe.copy()
    rows.loc[rows.index[:3], "y_0"] = 0.0
    monkeypatch.setitem(state.snapshot.__dict__, "universe", rows)
    d = client.get("/api/trending").json()
    assert sum(x["pct"] is None for x in d["items"]) == 3
    _check_forecast(d)


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


def test_topic_with_zero_views_on_asof_serializes_without_inf(client):
    """asof өдөр 0 уншилт (x_0 = 0) бол pct = inf байсан тул JSON үүсгэхэд сервер унадаг байв: одоо null, top-10-д орохгүй."""
    import json
    from app.main import state
    from src import serve
    rows = state.snapshot.universe.copy()
    zero = rows.index[:3]
    rows.loc[zero, "y_0"] = 0.0
    p = serve.ranked(serve.predict(state.model, rows))
    z = p[p["article"].isin(rows.loc[zero, "article"])]
    assert z["pct_h3"].isna().all() and z["rank"].isna().all() and z["arrow"].isna().all()
    hist = serve._histories(state.snapshot, z["article"], serve.LIST_DAYS)
    for r in z.itertuples():
        it = serve.item(r, hist[r.article], state.snapshot.asof)
        json.dumps(it, allow_nan=False)
        assert it["pct"] is None and all(f["pct"] is None for f in it["forecast"]) and not it["fire"]


def test_static_files_are_revalidated_so_css_matches_js(client):
    """Cache-Control-гүй бол браузер хуучин styles.css-ийг шинэ app.js-тэй хамт ашиглаж, загвар эвдэрдэг байв."""
    for f in ("styles.css", "app.js", "charts.js"):
        assert client.get(f"/static/{f}").headers["cache-control"] == "no-cache"
