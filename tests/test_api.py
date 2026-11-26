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


def _cyclical_rise(t) -> bool:
    """ADR 0019 JSON-ийн тоогоор: Rising, мөчлөг ≥ +10%, илүүдэл < +10% (5%-ийн алхмаар тэг рүү тайрсан тул хил хадгалагдана)."""
    return t["pct"] is not None and t["cycle"] is not None and t["pct"] >= 0.10 and t["cycle"] >= 0.10 and t["excess"] < 0.10


def test_trending_rank_is_the_beyond_list_at_most_10_without_cyclical_rises(client):
    """Давж өсөх жагсаалт (ADR 0019): хэмжигдэх, мөчлөгийн өсөлт биш Rising, pct-ээр, дээд тал нь 10, цөөн бол цөөн.
    `rank` нь энэ жагсаалтын байр, `beyond` нь дарааллаараа сэдвийн нэрс, items-ийн эхэнд."""
    d = client.get("/api/trending").json()
    assert d["mock"] is False
    top = [t for t in d["items"] if t["rank"] is not None]
    assert [t["article"] for t in top] == d["beyond"] == [t["article"] for t in d["items"][:len(top)]]
    assert [t["rank"] for t in top] == list(range(1, len(top) + 1)) and len(top) <= d["top_n"] == 10
    assert all(t["measurable"] and t["pct"] >= 0.10 and not t["cyclical"] for t in top)
    assert [t["pct"] for t in top] == sorted((t["pct"] for t in top), reverse=True)
    # Stable-аар нөхөхгүй: жагсаалт 10-аас цөөн бол үлдсэн хэмжигдэх Rising бүгд мөчлөгийн өсөлт
    if len(top) < 10:
        rest = [t for t in d["items"] if t["rank"] is None and t["measurable"] and t["pct"] is not None and t["pct"] >= 0.10]
        assert all(_cyclical_rise(t) for t in rest), [t["article"] for t in rest if not _cyclical_rise(t)]
    # 🔥 зөвхөн хэмжигдэх сэдэв ба pct ≥ T (харагдах pct нь тэг рүү тайрсан тул мөн ≥ T)
    assert all(t["measurable"] and t["pct"] >= d["T"] for t in d["items"] if t["fire"])


def test_trending_has_a_separate_cyclical_rise_list(client):
    """Мөчлөгийн өсөлтийн тусдаа жагсаалт: хэмжигдэх мөчлөгийн өсөлт бүгд, pct-ээр; Давж өсөх жагсаалттай давхцахгүй."""
    d = client.get("/api/trending").json()
    by = {t["article"]: t for t in d["items"]}
    cyc = [by[a] for a in d["cyclical_rise"]]
    assert all(t["measurable"] and t["cyclical"] and _cyclical_rise(t) for t in cyc)
    assert {t["article"] for t in d["items"] if t["measurable"] and _cyclical_rise(t)} == set(d["cyclical_rise"])
    assert [t["pct"] for t in cyc] == sorted((t["pct"] for t in cyc), reverse=True)
    assert not set(d["cyclical_rise"]) & set(d["beyond"])


def test_every_topic_has_cycle_excess_and_cyclical_flag(client):
    """ADR 0019: сэдэв бүрт мөчлөг, илүүдэл (5%-ийн алхмаар), мөчлөгийн өсөлт/бууралт эсэх."""
    items = client.get("/api/trending").json()["items"]
    for t in items:
        assert {"cycle", "excess", "cyclical"} <= set(t), t["article"]
        fall = (t["pct"] is not None and t["cycle"] is not None
                and t["pct"] <= -0.10 and t["cycle"] <= -0.10 and t["excess"] > -0.10)
        assert t["cyclical"] == (_cyclical_rise(t) or fall), t["article"]
    assert sum(t["cycle"] is not None for t in items) > 250       # 28+ хоногийн түүхтэй бараг бүх сэдэв
    assert any(t["cyclical"] for t in items)


def test_topic_page_cycle_matches_the_list(client):
    """/api/topic нь сэдвийн feature-ийг тусад нь тооцдог: мөчлөг, илүүдэл нь жагсаалтынхтай ижил."""
    t = client.get("/api/topic/ChatGPT").json()
    row = next(x for x in client.get("/api/trending").json()["items"] if x["article"] == "ChatGPT")
    assert (t["cycle"], t["excess"], t["cyclical"]) == (row["cycle"], row["excess"], row["cyclical"])
    assert t["cycle"] is not None


def test_home_chip_label_agrees_with_arrow_and_fires_count(client):
    """Нүүрний чип API-ийн label-ийг харуулна (#31): шошго сумаараа эхэлнэ, тайлбарын 🔥-ийн тоо чиптэй таарна."""
    d = client.get("/api/trending").json()
    for t in d["items"]:
        if t["pct"] is not None:
            assert t["label"].startswith(t["arrow"]), (t["article"], t["arrow"], t["label"])
            assert t["label"].startswith("🔥") == t["fire"]
    assert d["fires"] == sum(t["fire"] for t in d["items"] if t["rank"] is not None)   # тайлбар нь жагсаалтын 🔥


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


# ---------------------------------------------------------------- нөхцөл байдал ба дүгнэлт (ADR 0020, 0021, #51)

def test_every_topic_has_a_situation_code_and_only_anomalies_have_a_verdict(client):
    """Код нь ADR 0020-ийн 6 утгын нэг. Дүгнэлт (ADR 0021): Anomaly-д л, таамагласан pct (h3) ≤ −10% бол "унтрах".
    JSON-ийн pct нь 5%-ийн алхмаар тэг рүү тайрсан тул −10%-ийн хил хадгалагдана."""
    from src import situation
    items = client.get("/api/trending").json()["items"]
    for t in items:
        assert t["situation"] in situation.CODES and t["situation_label"] == situation.CODES[t["situation"]], t["article"]
        if not t["anomaly"] or t["pct"] is None:
            assert t["verdict"] is None and t["verdict_label"] is None and t["verdict_track"] is None, t["article"]
            continue
        assert t["verdict"] == ("fade" if t["pct"] <= -0.10 else "continue"), t["article"]
        assert t["verdict_label"] == situation.VERDICTS[t["verdict"]]
    assert any(t["verdict"] for t in items)


def test_each_anomaly_verdict_carries_its_recomputed_track_record_for_the_loaded_model(client):
    version = client.get("/api/model").json()["live"]["version"]
    full = client.get("/api/track-record").json()
    rec = next(s for s in full["sources"] if s["source_key"] == "recomputed" and s["model_version"] == version)
    by = {e["key"]: e for e in rec["by_verdict"]}
    for t in client.get("/api/trending").json()["items"]:
        if t["verdict"]:
            tr = t["verdict_track"]
            assert (tr["source"], tr["model_version"]) == ("сэргээж тооцсон", version)
            assert (tr["n"], tr["hit"], tr["base_hit"], tr.get("text")) == tuple(
                by[t["verdict"]].get(k) for k in ("n", "hit", "base_hit", "text"))


def test_trending_summarizes_the_days_anomalies_by_verdict(client):
    d = client.get("/api/trending").json()
    an = [t for t in d["items"] if t["verdict"]]
    s = d["anomalies"]
    assert s["n"] == len(an) and s["continue"] == sum(t["verdict"] == "continue" for t in an)
    assert s["fade"] == s["n"] - s["continue"] and s["all_fade"] == (s["n"] > 0 and s["continue"] == 0)


def test_topic_page_has_the_same_situation_and_verdict_as_the_list(client):
    by = {t["article"]: t for t in client.get("/api/trending").json()["items"]}
    t = client.get("/api/topic/ChatGPT").json()
    assert (t["situation"], t["verdict"]) == (by["ChatGPT"]["situation"], by["ChatGPT"]["verdict"])


def test_track_record_endpoint_gives_tables_per_source_and_model_version(client):
    """"Хэр найдвартай вэ?" (ADR 0020): эх сурвалж бүр (сэргээж тооцсон / хадгалсан) model хувилбартай, тусдаа."""
    from src import situation
    d = client.get("/api/track-record").json()
    assert d["model_version"] == client.get("/api/model").json()["live"]["version"]
    assert d["sources"] and d["min_n"] == situation.MIN_N
    for s in d["sources"]:
        assert s["source"] == situation.SOURCES[s["source_key"]] and s["model_version"].startswith("v")
        assert s["current"] == (s["model_version"] == d["model_version"])
        assert [e["key"] for e in s["by_code"]] == list(situation.CODES)
        assert [e["key"] for e in s["by_band"]] == list(situation.BANDS)
        assert [e["key"] for e in s["by_verdict"]] == list(situation.VERDICTS)
        for e in s["by_code"] + s["by_band"] + s["by_verdict"]:
            assert e["enough"] == (e["n"] >= situation.MIN_N)
            assert (e["up10"] is None) == (not e["enough"]) and (e.get("text") == "хангалтгүй") == (not e["enough"])


# ---------------------------------------------------------------- W7 (#52): ● өдрүүд, өгөгдөл дутуу өдөр

def test_every_topic_carries_its_anomaly_days_within_its_history(client):
    """● = өнгөрсөн Anomaly (ADR 0024): spark (нүүр) ба гол графикийн (сэдвийн хуудас) тэмдэг. `anom` = [{d, r}], history-ийн
    өдрүүдээс. asof өдөр нь `anom`-д байх ⇔ сэдвийн `anomaly`, ×N нь `ratio`-тай ижил (feature_rows-ийн замаар тооцсон)."""
    d = client.get("/api/trending").json()
    seen = 0
    for t in d["items"]:
        days = {h["d"] for h in t["history"]}
        an = {a["d"]: a["r"] for a in t["anom"]}
        assert set(an) <= days, t["article"]
        assert (d["asof"] in an) == t["anomaly"], t["article"]
        if t["anomaly"]:
            assert an[d["asof"]] == t["ratio"], t["article"]
        seen += len(an)
    assert seen > sum(t["anomaly"] for t in d["items"])   # өмнөх өдрүүдийн ● ч бий


def test_topic_page_anomaly_days_span_its_history_and_agree_with_the_list(client):
    by = {t["article"]: t for t in client.get("/api/trending").json()["items"]}
    picks = [a for a, t in by.items() if t["anom"]][:3] + ["ChatGPT"]
    for a in picks:
        t = client.get(f"/api/topic/{a}").json()
        days = [h["d"] for h in t["history"]]
        an = {x["d"]: x["r"] for x in t["anom"]}
        assert set(an) <= set(days)
        recent = {k: v for k, v in an.items() if k >= by[a]["history"][0]["d"]}
        assert recent == {x["d"]: x["r"] for x in by[a]["anom"]}, a


@pytest.mark.parametrize("status, incomplete", [("not_published", True), ("partial", True), ("ok", False), ("error", False), (None, False)])
def test_responses_name_the_day_that_has_not_arrived_complete(client, monkeypatch, status, incomplete):
    """ADR 0022 "Өгөгдөл дутуу": Wikimedia-аас татахад asof + 1 өдөр бүрэн ирээгүй (сервер тэр өдрийг cache-д нэмдэггүй) бол
    `incomplete` = тэр өдөр, нүүр "11.10-ны өгөгдөл бүрэн ирээгүй. 11.09-ний дүнг харуулж байна." гэнэ. Бусад үед null.
    Татах алдаа (error) нь "дутуу" биш: тэр үед зөвхөн хуучирсан (`stale`) эсэхийг харуулна."""
    import app.main as m
    monkeypatch.setitem(m.state.refresh, "status", status)
    for ep in ("/api/trending", "/api/map", "/api/topic/ChatGPT"):
        d = client.get(ep).json()
        want = (pd.Timestamp(d["asof"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if incomplete else None
        assert d["incomplete"] == want, ep


# ---------------------------------------------------------------- W7 (#52): сэдвийн хуудасны replay (ADR 0015, 0026, 0027)

def test_topic_replay_is_the_as_of_forecast_of_each_past_day(client):
    """Өнгөрсөн өдөр D (asof−3 … asof−24) бүрийн таамаг = D хүртэл тайрсан түүхий өгөгдлөөр сервертэй ижил замаар тооцсон
    сэргээж тооцсон таамаг (`src.backtest.replay`, ADR 0015). D+3-ын бодит утга харагдах өдрүүд л: шинээс хуучин руу."""
    from app import main as m
    from src import backtest, live
    d = client.get("/api/topic/ChatGPT/replay").json()
    asof = pd.Timestamp(d["asof"])
    days = [r["asof"] for r in d["items"]]
    assert days == [(asof - pd.Timedelta(days=k)).strftime("%Y-%m-%d") for k in range(3, 25)]
    assert d["source"] == "сэргээж тооцсон" and d["model_version"].startswith("v")
    raw = live.RawCache.load(m.PROCESSED)
    for r in (d["items"][0], d["items"][-1]):
        want = backtest.replay(raw, m.state.model, pd.Timestamp(r["asof"])).set_index("article").loc["ChatGPT"]
        assert [f["d"] for f in r["forecast"]] == [(pd.Timestamp(r["asof"]) + pd.Timedelta(days=h)).strftime("%Y-%m-%d") for h in (1, 2, 3)]
        assert [f["y"] for f in r["forecast"]] == [round(want[f"views_h{h}"]) for h in (1, 2, 3)]
        assert [(f["lo"], f["hi"]) for f in r["forecast"]][2] != (None, None)
        assert r["anomaly"] == bool(want["anomaly"]) and r["verdict"] == (None if pd.isna(want["verdict"]) else want["verdict"])


def test_replay_of_an_unknown_topic_is_404(client):
    assert client.get("/api/topic/No_such_topic_xyz/replay").status_code == 404


def test_topic_page_carries_the_strong_rise_threshold_of_the_list(client):
    """Хүчтэй өсөлт тод (ADR 0026): сэдвийн хуудас нүүртэй ижил босгоор (`T`) тодруулна."""
    assert client.get("/api/topic/ChatGPT").json()["T"] == client.get("/api/trending").json()["T"]
