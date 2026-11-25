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


def test_forecast_dates_text_is_month_dot_day_zero_padded(client):
    """ADR 0018: хугацааны муж "11.11–11.13" (сар.өдөр, тэгээр нөхсөн), "11/11–11/13" биш."""
    d = client.get("/api/trending").json()
    f = pd.date_range(d["asof"], periods=4)[1:]
    assert d["dates"] == f"{f[0]:%m.%d}–{f[-1]:%m.%d}"
    assert client.get("/api/model").json()["dates"] == d["dates"]


def test_forecast_dates_text_across_new_year_and_single_digit_days():
    from src import serve
    assert serve.dates_text(pd.Timestamp("2026-11-08")) == "11.09–11.11"
    assert serve.dates_text(pd.Timestamp("2026-12-30")) == "12.31–01.02"


def test_no_api_text_has_a_slash_date(client):
    """ADR 0018: /api/*-ийн ямар ч текстэд "11/9", "11/11–11/13" маягийн огноо үлдээгүй."""
    import re
    slash = re.compile(r"(?<![\d/])\d{1,2}/\d{1,2}(?![\d/])")

    def strings(v):
        if isinstance(v, str):
            yield v
        elif isinstance(v, dict):
            for x in v.values():
                yield from strings(x)
        elif isinstance(v, list):
            for x in v:
                yield from strings(x)
    for ep in ("/api/trending", "/api/topic/ChatGPT", "/api/map", "/api/categories", "/api/model"):
        hits = [x for x in strings(client.get(ep).json()) if slash.search(x)]
        assert not hits, (ep, hits[:3])


def test_forecast_has_concrete_dates_interval_and_no_viral_category(client):
    _check_forecast(client.get("/api/trending").json())


def test_forecast_check_holds_when_some_topics_have_zero_views_on_asof(client, monkeypatch):
    """Майкийн data/live/ cache-д 11/09-нд WWE_Bash_in_Berlin = 0 уншилт байсан (PR #21: pct/interval = null).
    data/live/-гүй орчинд ч энэ тохиолдлыг давтахын тулд хэдэн сэдвийн x_0-г 0 болгоно."""
    from app.main import state
    rows = state.snapshot.universe.copy()
    rows.loc[rows.index[:3], "y_0"] = 0.0
    n_zero = int((rows["y_0"] == 0).sum())   # + өгөгдөлд аль хэдийн 0 уншилттай сэдвүүд (жишээ нь 11/10-нд 2 сэдэв)
    monkeypatch.setitem(state.snapshot.__dict__, "universe", rows)
    d = client.get("/api/trending").json()
    assert sum(x["pct"] is None for x in d["items"]) == n_zero
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
    # Model хувилбар (ADR 0015, #44): ачаалсан файлуудын hash, UI-д богино нь
    from src import train
    assert live["model_hash"] == train.model_hash(train.MODEL_DIR)
    assert live["version"] == "v" + live["model_hash"][:7]
    assert m["winner"] == "catboost" and m["metrics"] and m["test_end"]
    # "Яаж хийсэн бэ?": бүх тоо meta.json / өгөгдлөөс
    p = m["pipeline"]
    assert p["topics"] == 301 and p["n_features"] == 18 and p["purge_days"] == 3 and p["trials"] == 225
    assert p["algo_name"] == "CatBoost" and p["clean_rows"] > 0 and p["naive_h3"]["valid"] < p["naive_h3"]["train"]
    assert m["names"]["naive"] == "Одоогийнхтой адилхан" and set(m["valid"]["mean"]) == {"lightgbm", "xgboost", "catboost", "naive"}
    # Загвар хуудасны бүлгийн нэрс (#34): сэдвийн тоо бүлэг бүрээр, нийлбэр нь нийт сэдэв
    assert p["topics_groups"] == {"а": 151, "б": 114, "в": 36} and sum(p["topics_groups"].values()) == p["topics"]


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


ANOMALY_FIELDS = ("z", "anomaly", "ratio", "views_ratio", "normal", "typical_pct", "similar_days")


def test_every_topic_has_anomaly_fields_and_anomaly_iff_z_at_least_3(client):
    """ADR 0017 (#48): z, anomaly, ×N (анхаарал), уншилтын ×N, ердийн өдөр, ердийн хэлбэлзэл, "ийм өдөр хэдэн удаа"."""
    items = client.get("/api/trending").json()["items"]
    for t in items:
        assert all(k in t for k in ANOMALY_FIELDS), t["article"]
        if t["z"] is None:
            assert t["anomaly"] is False
        else:   # z нь JSON-д 2 оронтой
            assert t["anomaly"] == (t["z"] >= 3) or abs(t["z"] - 3) <= 0.005, (t["article"], t["z"])
    n = sum(t["anomaly"] for t in items)
    assert 5 <= n <= 60, n      # valid дээр хэмжигдэх сэдэвт өдөрт ~19.6 (8 … ~39)


def test_normal_is_median_views_of_days_t59_to_t7_not_derived_from_ratio(client):
    """"Ердийн өдөр"-ийн тоо API-ийн `normal`-оос: /api/topic-ийн өөрийн 180 өдрийн түүхийн t−59 … t−7 өдрийн медиан уншилт.
    ratio нь одоо анхаарал дээр тул views / ratio нь ердийн өдрийн уншилт биш."""
    import statistics
    t = client.get("/api/topic/ChatGPT").json()
    v = [h["v"] for h in t["history"]]
    assert t["history"][-1]["d"] == t["asof"]
    want = statistics.median(v[-60:-7])            # t−59 … t−7 = 53 өдөр
    assert t["normal"] == round(want)
    assert t["views_ratio"] == round(t["views"] / want, 1)
    assert t["typical_pct"] > 0 and isinstance(t["similar_days"], int)


def test_responses_carry_total_views_note_field(client):
    """Нийт уншилтын |z| ≥ 4 өдөр л мөртэй (src/anomaly.total_note), бусад үед null."""
    for ep in ("/api/trending", "/api/categories", "/api/map", "/api/topic/ChatGPT"):
        d = client.get(ep).json()
        assert "total_note" in d
        assert d["total_note"] is None or d["total_note"]["text"].startswith("Энэ өдөр Wikipedia-ийн нийт уншилт")
