"""Сэргээж тооцсон backtest (ADR 0015, #50): as-of replay нь D-ээс хойшхи өгөгдлөөс хамаарахгүй, сүүлийн өдөр сервертэй
ижил, гаралт model хувилбартай.  pytest -q"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["SHUUGIAN_REFRESH"] = "0"
from src import backtest, clean, live, serve, train  # noqa: E402

D = pd.Timestamp("2026-06-15")
SPIKY = "Taylor_Swift"


@pytest.fixture(scope="module")
def raw() -> live.RawCache:
    return live.RawCache.load(ROOT / "data" / "processed")


@pytest.fixture(scope="module")
def model():
    return train.load()


def subset(raw: live.RawCache, articles) -> live.RawCache:
    """Хурдны тулд цөөн сэдэв (сэдэв бүр бие даан цэвэрлэгддэг тул replay-ийн утга өөрчлөгдөхгүй)."""
    keep = lambda df: df[df["article"].isin(articles)].reset_index(drop=True)   # noqa: E731
    return live.RawCache(keep(raw.pageviews), keep(raw.alias), raw.total)


def edit(raw: live.RawCache, fn_pv, fn_total=lambda t: t, fn_alias=lambda a: a) -> live.RawCache:
    return live.RawCache(fn_pv(raw.pageviews.copy()), fn_alias(raw.alias.copy()), fn_total(raw.total.copy()))


def test_replay_of_day_d_ignores_every_raw_row_after_d(raw, model):
    """D өдөр SPIKY-д ганц өдрийн огцом өсөлт. D+1 нь бага бол бүтэн түүхээр цэвэрлэхэд D хязгаарлагдана (look-ahead),
    D+1 өндөр бол үгүй. As-of replay хоёр тохиолдолд ЯГ ижил байх ёстой, D-ээс хойшхи бүх мөрийг өөрчилсөн ч."""
    aliased = sorted(raw.alias["article"].unique())
    arts = sorted(set(raw.pageviews["article"].unique()[:15]) | set(aliased) | {SPIKY})
    small = subset(raw, arts)
    pv = small.pageviews
    is_x = pv["article"] == SPIKY
    med = int(pv.loc[is_x & (pv["date"] <= D), "views"].tail(29).median())

    def spike_at_d(p):
        p.loc[(p["article"] == SPIKY) & (p["date"] == D), "views"] = 50 * med
        return p

    def quiet_after(p):   # D+1 = медиан -> бүтэн түүхээр бол D тусгаарлагдсан өсөлт
        p = spike_at_d(p)
        p.loc[(p["article"] == SPIKY) & (p["date"] == D + pd.Timedelta(days=1)), "views"] = med
        return p

    def loud_after(p):    # D-ээс хойш бүх мөр өөр: ×3, SPIKY-д D+1 өндөр, зарим мөр алга
        p = spike_at_d(p)
        after = p["date"] > D
        p.loc[after, "views"] = p.loc[after, "views"] * 3
        p.loc[(p["article"] == SPIKY) & (p["date"] == D + pd.Timedelta(days=1)), "views"] = 50 * med
        return p[~(after & (p["date"].dt.day % 5 == 0))].reset_index(drop=True)

    a = edit(small, quiet_after)
    b = edit(small, loud_after,
             lambda t: t.assign(total_views=np.where(t["date"] > D, t["total_views"] // 2, t["total_views"])),
             lambda al: al.assign(views=np.where(al["date"] > D, al["views"] * 7 + 1000, al["views"])))
    assert (b.alias["date"] > D).any() and not b.alias.equals(a.alias)

    # Шалгалтын шүд: бүтэн түүхээр цэвэрлэвэл D өдрийн утга хоёр тохиолдолд өөр (тиймээс бэлэн хүснэгтээс тооцохгүй).
    full = lambda r: clean.clean_frame(r.pageviews, r.alias, r.total)[0].set_index(["article", "date"])   # noqa: E731
    assert full(a).loc[(SPIKY, D), "y"] != full(b).loc[(SPIKY, D), "y"]

    ra, rb = backtest.replay(a, model, D), backtest.replay(b, model, D)
    assert len(ra) == len(arts) and (ra["asof"] == D).all()
    assert SPIKY in set(ra["article"])
    pd.testing.assert_frame_equal(ra, rb)


def test_replay_of_last_day_equals_the_servers_forecast_that_day(raw, model):
    """Сүүлийн asof (= data/processed-ийн сүүлийн өдөр) дээрх replay нь сервер (app/main.py) тэр өдөр гаргасан таамагтай
    ЯГ таарна: бүтэн нарийвчлалаар (Snapshot -> predict) ба /api/trending-ийн хэлбэрээр (pct 5%-д тайрсан, уншилт бүхэлчилсэн)."""
    from fastapi.testclient import TestClient

    import app.main as m

    with TestClient(m.app) as c:
        api = c.get("/api/trending").json()
        server = serve.predict(m.state.model, m.state.snapshot.universe)
    rep = backtest.replay(raw, model, raw.end)
    assert api["asof"] == str(raw.end.date())

    srv = server.set_index(server["article"].astype(str)).sort_index()
    ours = rep.set_index("article").sort_index()
    assert list(ours.index) == list(srv.index) and len(ours) > 0.9 * raw.pageviews["article"].nunique()
    for h in backtest.HORIZONS:
        for col in ("delta_hat", "pct", "lo", "hi", "views"):
            np.testing.assert_array_equal(ours[f"{col}_h{h}"].to_numpy(), srv[f"{col}_h{h}"].to_numpy(dtype=float))
    assert ours["arrow"].tolist() == srv["arrow"].tolist()   # None (x_0 = 0) == None

    for it in api["items"]:
        r = ours.loc[it["article"]]
        assert [f["pct"] for f in it["forecast"]] == [serve._r(r[f"pct_h{h}"]) for h in backtest.HORIZONS]
        assert [f["y"] for f in it["forecast"]] == [round(r[f"views_h{h}"]) for h in backtest.HORIZONS]


def test_boundary_is_the_first_test_day_and_is_pinned_to_the_model_version(model):
    """Хил (ADR 0015, 1-р дүрэм) нь тохиргоонд, тэр model хувилбартай хамт. Model-ийг дахин сургавал (эсвэл calibrate.py
    meta.json-ийг дахин бичвэл) hash өөрчлөгдөж, хилийг шинэчлэх хүртэл backtest ажиллахгүй."""
    import dataclasses

    assert backtest.boundary(model) == pd.Timestamp("2026-04-01")
    assert backtest.boundary(model) == pd.Timestamp(model.meta["test"]["test_start"])
    retrained = dataclasses.replace(model, model_hash="0" * 64)
    with pytest.raises(backtest.BoundaryOutdated, match="хил"):
        backtest.boundary(retrained)


SAMPLE = ["Donald_Trump", "Joe_Biden", "UFC_266", "Hideki_Matsuyama", "Charlie_Kirk_(activist)", "Black_Sabbath"]   # а, а, б, б, в, в


def test_run_writes_versioned_rows_with_actuals_and_a_grouped_summary(tmp_path, raw, model):
    """Гаралт: asof (хилээс) × сэдэв мөр бүр model хувилбартай, бүлэгтэй, бодит утгатай (D+h өгөгдөл байвал).
    Тайлан нь бүлгээр, гол нь (а), үлдэх хазайлттай."""
    end = backtest.FROM + pd.Timedelta(days=4)
    data = backtest.truncate(subset(raw, SAMPLE), end)
    res = backtest.run(data, model, tmp_path)
    out = pd.read_parquet(res["path"])

    assert res["path"].parent.name == train.short_version(model.model_hash)
    assert sorted(out["asof"].unique()) == list(pd.date_range(backtest.FROM, end))
    assert len(out) == 5 * len(SAMPLE)
    assert (out["model_hash"] == model.model_hash).all() and (out["model_version"] == res["model_version"]).all()
    assert dict(zip(out["article"], out["group"])) == dict(zip(SAMPLE, "ааббвв"))

    # Бодит утга (worked example, alias-гүй, огцом өсөлтгүй сэдэв): анхаарал = уншилт / нийт уншилт.
    pv = raw.pageviews.set_index(["article", "date"])["views"]
    tot = raw.total.set_index("date")["total_views"]
    att = lambda d: pv[("Donald_Trump", d)] / tot[d]   # noqa: E731
    r = out[(out["article"] == "Donald_Trump") & (out["asof"] == backtest.FROM)].iloc[0]
    for h in backtest.HORIZONS:
        d = backtest.FROM + pd.Timedelta(days=h)
        assert r[f"actual_pct_h{h}"] == pytest.approx(att(d) / att(backtest.FROM) - 1, rel=1e-9)
        assert r[f"actual_views_h{h}"] == pv[("Donald_Trump", d)]
    # D + h нь өгөгдлөөс хойш бол бодит утгагүй
    last = out[out["asof"] == end]
    assert last[[f"actual_pct_h{h}" for h in backtest.HORIZONS]].isna().all().all()
    assert out.loc[out["asof"] == end - pd.Timedelta(days=1), "actual_pct_h1"].notna().all()

    s = res["summary"]
    assert s["model_hash"] == model.model_hash and s["from"] == "2026-04-01" and s["through"] == str(end.date())
    assert s["source"] == "сэргээж тооцсон" and s["main_group"] == "а"
    assert set(s["groups"]) == {"а", "б", "в"}
    g = s["groups"]["а"]
    assert g["topics"] == 2 and g["h1"]["rows"] == 2 * 4 and g["h3"]["rows"] == 2 * 2
    assert {"model", "naive"} <= set(g["h1"]["mae"]) and "coverage" in g["h1"] and "skill" in g["h1"]
    assert any("(в)" in c for c in s["caveats"])
    assert (res["path"].parent / "summary.json").exists()


def test_rerun_skips_computed_days_and_fills_actuals_that_became_available(tmp_path, raw, model):
    small = subset(raw, SAMPLE[:2])
    first = backtest.run(backtest.truncate(small, backtest.FROM + pd.Timedelta(days=2)), model, tmp_path)
    assert first["computed"] == 3
    again = backtest.run(backtest.truncate(small, backtest.FROM + pd.Timedelta(days=4)), model, tmp_path)
    assert again["computed"] == 2
    out = pd.read_parquet(again["path"])
    assert sorted(out["asof"].unique()) == list(pd.date_range(backtest.FROM, periods=5))
    # өмнөх ажиллагааны сүүлийн өдөр бодит утгагүй байсан, одоо h1–h2 нь бий
    assert out.loc[out["asof"] == backtest.FROM + pd.Timedelta(days=2), "actual_pct_h2"].notna().all()
    assert backtest.run(backtest.truncate(small, backtest.FROM + pd.Timedelta(days=4)), model, tmp_path)["computed"] == 0


def test_rows_of_another_model_version_are_never_mixed_in(tmp_path, raw, model):
    small = backtest.truncate(subset(raw, SAMPLE[:1]), backtest.FROM + pd.Timedelta(days=1))
    path = backtest.run(small, model, tmp_path)["path"]
    other = pd.read_parquet(path).assign(model_hash="f" * 64)
    other.to_parquet(path, index=False)
    with pytest.raises(ValueError, match="хувилбар"):
        backtest.run(small, model, tmp_path)
