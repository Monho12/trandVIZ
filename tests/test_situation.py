"""Нөхцөл байдлын код, "үргэлжлэх / унтрах" дүгнэлт, track record (ADR 0020, 0021, #51).  pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import situation  # noqa: E402


# ---------------------------------------------------------------- дүгнэлт (ADR 0021, "Тодорхойлолт")

@pytest.mark.parametrize("pct, anomaly, want", [
    (-0.10, True, "fade"),        # ≤ −10% -> унтрах (хил орно)
    (-0.35, True, "fade"),
    (-0.0999, True, "continue"),  # бусад бүх тохиолдол -> үргэлжлэх
    (0.0, True, "continue"),
    (0.40, True, "continue"),
    (-0.35, False, None),         # Anomaly биш сэдэвт дүгнэлт байхгүй
    (np.nan, True, None),         # таамаг тодорхойгүй (x_0 = 0)
])
def test_verdict_is_fade_iff_predicted_h3_pct_at_most_minus_10_and_only_for_anomalies(pct, anomaly, want):
    assert situation.verdict([pct], [anomaly]).tolist() == [want]


def test_verdict_labels_are_neutral_words():
    assert situation.VERDICTS == {"continue": "үргэлжлэх", "fade": "унтрах"}


# ---------------------------------------------------------------- нөхцөл байдлын код (ADR 0020, #51)

L95, L105 = np.log(0.95), np.log(1.05)   # 7 хоногийн (лог) дунджаас 5% доор / дээр

QUIET = dict(ratio_7=0.0, growth_3=0.0, z=0.0, peak_z=0.0, peak_y=1.0, y_0=1.0, cyclical=False, total_day=False)


def code_of(**kw) -> str:
    return situation.code(pd.DataFrame([{**QUIET, **kw}]))[0]


def test_rebound_is_5_pct_below_7_day_mean_and_not_an_anomaly():
    assert code_of(ratio_7=L95 - 1e-9) == "rebound"
    assert code_of(ratio_7=L95 + 1e-3) == "unclear"
    assert code_of(ratio_7=-0.5, z=3.0, peak_z=4.0, peak_y=3.0, y_0=2.0) == "after_peak"   # Anomaly бол Буцалт биш


def test_after_peak_needs_an_anomaly_in_the_last_7_days_and_today_below_that_peak():
    assert code_of(peak_z=3.0, peak_y=2.0, y_0=1.5) == "after_peak"
    assert code_of(peak_z=2.9, peak_y=2.0, y_0=1.5) == "unclear"          # 7 хоногт Anomaly байгаагүй
    assert code_of(peak_z=5.0, peak_y=2.0, y_0=2.0, ratio_7=0.3, growth_3=0.2) == "growing"   # оргилоосоо доор биш


def test_growing_is_5_pct_above_7_day_mean_and_higher_than_3_days_ago():
    assert code_of(ratio_7=L105, growth_3=0.01) == "growing"
    assert code_of(ratio_7=L105, growth_3=0.0) == "unclear"
    assert code_of(ratio_7=L105 - 1e-3, growth_3=0.3) == "unclear"


def test_total_views_day_comes_first_then_cycle_then_rebound():
    assert code_of(total_day=True, cyclical=True, ratio_7=-0.5) == "total"
    assert code_of(cyclical=True, ratio_7=-0.5) == "cycle"
    assert code_of(ratio_7=-0.5, peak_z=4.0, peak_y=3.0, y_0=1.0) == "rebound"   # Anomaly биш бол Буцалт түрүүлнэ


def test_undefined_inputs_never_raise_and_fall_to_unclear():
    nan = float("nan")
    assert code_of(ratio_7=nan, growth_3=nan, z=nan, peak_z=nan, peak_y=nan) == "unclear"


def test_code_labels_describe_conditions_not_causes():
    assert situation.CODES == {"total": "Нийт уншилтын нөлөө", "cycle": "Мөчлөг", "rebound": "Буцалт",
                               "after_peak": "Оргилын дараах бууралт", "growing": "Үргэлжилж буй өсөлт",
                               "unclear": "Тодорхой бус"}
    assert not any("шалтгаан" in v.lower() for v in situation.CODES.values())


def test_recent_peak_is_max_z_and_max_y_over_t_minus_7_to_t_minus_1_per_topic():
    dates = pd.date_range("2026-01-01", periods=10)
    y = [1, 1, 5, 1, 1, 1, 1, 1, 1, 9]          # оргил 01-03 (y 5, z 4), 01-10 нь өөрөө (t) цонхонд орохгүй
    z = [0, 0, 4, 0, 0, 0, 0, 0, 0, 8]
    a = pd.DataFrame({"article": "a", "date": dates, "y": y, "z": z})
    b = a.assign(article="b", y=1.0, z=0.0)        # өөр сэдэв: a-ийн оргил нэвчихгүй
    df = pd.concat([b, a], ignore_index=True)
    got = situation.recent_peak(df)
    a10 = df.index[(df["article"] == "a") & (df["date"] == dates[9])][0]
    a11 = df.index[(df["article"] == "a") & (df["date"] == dates[2])][0]
    assert got.loc[a10].tolist() == [4.0, 5.0]       # t−7 = 01-03 цонхонд
    assert got.loc[a11].tolist() == [0.0, 1.0]       # 01-03-ийн өөрийн утга орохгүй
    assert (got.loc[df["article"] == "b", "peak_z"].fillna(0) == 0).all()
    assert np.isnan(got.loc[df.index[(df["article"] == "a") & (df["date"] == dates[0])][0], "peak_z"])   # түүхгүй


def test_peak_window_drops_day_t_minus_8():
    dates = pd.date_range("2026-01-01", periods=9)
    df = pd.DataFrame({"article": "a", "date": dates, "y": [5] + [1] * 8, "z": [4] + [0] * 8})
    assert situation.recent_peak(df).iloc[-1].tolist() == [0.0, 1.0]


# ---------------------------------------------------------------- (в)-гүй valid дээр ADR 0020, 0021-ийн тоо

@pytest.fixture(scope="module")
def valid():
    """calibrate.valid_frame ((в)-гүй valid, хэмжигдэх), Anomaly (z), сүүлийн 7 хоногийн оргил, мөчлөг, нийт уншилтын өдөр,
    код, дүгнэлт ба бодит pct (h3). Image-ийн data/processed-оос санах ойд (tests/test_cycle.py-тэй ижил)."""
    from src import anomaly, calibrate, cycle, features, live, scoring, serve, train
    raw = live.RawCache.load(ROOT / "data" / "processed")
    cl = pd.concat(list(serve.clean_chunks(raw)), ignore_index=True)
    va = calibrate.valid_frame(train.load(), features.frame(cl), cl)
    an = anomaly.score(cl)
    extra = cl[["article", "date", "y"]].assign(z=an["z"].to_numpy(), anomaly=an["anomaly"].to_numpy(),
                                                 cycle=cycle.cycle(cl).to_numpy())
    extra = pd.concat([extra, situation.recent_peak(extra)], axis=1).drop(columns="y")
    va = va.merge(extra, on=["article", "date"], how="left")
    total = cl.drop_duplicates("date")[["date", "total_views"]]
    va["total_day"] = va["date"].map({d: anomaly.total_note(total, d) is not None for d in va["date"].unique()})
    p = va["pred_pct"]
    va["cyclical"] = cycle.is_cyclical_rise(p, va["cycle"]) | cycle.is_cyclical_fall(p, va["cycle"])
    va["situation"] = situation.code(va)
    va["verdict"] = situation.verdict(p, va["anomaly"])
    va["actual_pct"] = scoring.pct(va["y_0"], va["y_h3"])
    return va[va["measurable"].fillna(False).astype(bool)]


def test_valid_ordinary_rising_codes_match_adr_0020(valid):
    """ADR 0020: жирийн Rising (мөчлөгийн өсөлт биш) өдөрт 14.1, үүний Буцалт 95%, тодорхой бус 4%, Үргэлжилж буй өсөлт 1%."""
    from src import cycle
    days = valid["date"].nunique()
    p = valid["pred_pct"]
    ordinary = valid[(p >= 0.10) & ~cycle.is_cyclical_rise(p, valid["cycle"])]
    share = ordinary["situation"].value_counts(normalize=True)
    assert days == 271 and len(ordinary) / days == pytest.approx(14.1, abs=0.05)
    assert share["rebound"] == pytest.approx(0.95, abs=0.01)
    assert share["unclear"] == pytest.approx(0.04, abs=0.01)
    assert share["growing"] == pytest.approx(0.01, abs=0.005)
    assert "cycle" not in share     # мөчлөгийн өсөлтийг хассан тул


def test_valid_anomalies_are_never_rebound(valid):
    a = valid[valid["anomaly"]]
    assert len(a) and not (a["situation"] == "rebound").any()


def test_valid_verdicts_reproduce_adr_0021(valid):
    """ADR 0021 (тодорхойлолтоор: дүгнэлт h3 ≤ −10%, бодит үр дүн h3): anomaly өдөрт 19.6, "үргэлжлэх" 3.8, тэдний 60.8% нь
    унтраагүй (үндсэн хувь 30.5%), "үргэлжлэх" 0-тэй өдөр 271-ээс 8, 1-тэй нь 31."""
    a = valid[valid["anomaly"]]
    days = valid["date"].nunique()
    cont = a["verdict"] == "continue"
    not_faded = a["actual_pct"] > -0.10
    assert len(a) / days == pytest.approx(19.6, abs=0.05)
    assert cont.sum() / days == pytest.approx(3.8, abs=0.05)
    assert not_faded[cont].mean() == pytest.approx(0.608, abs=0.0005)
    assert not_faded.mean() == pytest.approx(0.305, abs=0.0005)
    per_day = cont.groupby(a["date"]).sum().reindex(valid["date"].unique(), fill_value=0)
    assert ((per_day == 0).sum(), (per_day == 1).sum()) == (8, 31)


# ---------------------------------------------------------------- таамгийн зурвас ба track record

@pytest.mark.parametrize("pct, want", [
    (-0.20, "le_-20"), (-0.50, "le_-20"), (-0.1999, "-20_-10"), (-0.10, "-20_-10"), (-0.0999, "pm10"),
    (0.0999, "pm10"), (0.10, "10_25"), (0.2499, "10_25"), (0.25, "ge_25"), (1.5, "ge_25"), (np.nan, None)])
def test_band_edges_follow_the_site_arrows(pct, want):
    assert situation.band([pct]).tolist() == [want]


def test_band_labels():
    assert list(situation.BANDS.values()) == ["≤ −20%", "−20…−10%", "±10%", "+10…+25%", "≥ +25%"]


H = "a" * 64


def rows(n, **kw) -> pd.DataFrame:
    base = dict(asof=pd.Timestamp("2026-05-01"), article="x", measurable=True, group="а", model_hash=H,
                pct_h3=0.0, actual_pct_h3=0.0, cycle=0.0, situation="unclear", anomaly=False, verdict=None)
    return pd.DataFrame([{**base, **kw}] * n)


def entry(table: list, key: str) -> dict:
    return next(e for e in table if e["key"] == key)


def test_outcome_shares_are_counted_from_actual_h3_pct_and_excess_over_cycle():
    # 20 Буцалт: бодит +30% (10), +5% (5), −15% (5). Мөчлөг +20%: +30% -> илүүдэл +8% (< 10%), харин мөчлөг 0 бол +30%.
    d = pd.concat([rows(10, situation="rebound", actual_pct_h3=0.30, cycle=0.20),
                   rows(5, situation="rebound", actual_pct_h3=0.05),
                   rows(5, situation="rebound", actual_pct_h3=-0.15),
                   rows(25, situation="unclear", actual_pct_h3=0.30)], ignore_index=True)
    t = situation.track_record(d, "recomputed")
    e = entry(t["by_code"], "rebound")
    assert e["label"] == "Буцалт" and e["n"] == 20 and e["enough"]
    assert (e["up10"], e["up"], e["down10"], e["excess10"]) == (0.5, 0.75, 0.25, 0.0)
    assert t["base"]["n"] == 45 and t["base"]["up10"] == pytest.approx(35 / 45, abs=1e-4)


def test_fewer_than_20_rows_say_insufficient_instead_of_numbers():
    t = situation.track_record(pd.concat([rows(19, situation="growing"), rows(30)], ignore_index=True), "recomputed")
    e = entry(t["by_code"], "growing")
    assert e == {"key": "growing", "label": "Үргэлжилж буй өсөлт", "n": 19, "enough": False, "text": "хангалтгүй",
                 "up10": None, "up": None, "down10": None, "excess10": None}
    assert entry(t["by_code"], "total")["n"] == 0 and t["min_n"] == 20


def test_every_band_and_code_is_listed_even_when_empty():
    t = situation.track_record(rows(25), "recomputed")
    assert [e["key"] for e in t["by_code"]] == list(situation.CODES)
    assert [e["key"] for e in t["by_band"]] == list(situation.BANDS)
    assert entry(t["by_band"], "pm10")["n"] == 25


def test_verdict_track_record_has_hit_rate_and_base_rate_of_all_anomalies():
    # 30 "үргэлжлэх": 18 унтраагүй (60%). 70 "унтрах": 56 унтарсан (80%). Бүх 100 anomaly-ийн 32 нь унтраагүй, 68 нь унтарсан.
    d = pd.concat([rows(18, anomaly=True, verdict="continue", actual_pct_h3=0.0),
                   rows(12, anomaly=True, verdict="continue", actual_pct_h3=-0.3),
                   rows(56, anomaly=True, verdict="fade", pct_h3=-0.3, actual_pct_h3=-0.3),
                   rows(14, anomaly=True, verdict="fade", pct_h3=-0.3, actual_pct_h3=0.1),
                   rows(50)], ignore_index=True)
    t = situation.track_record(d, "recomputed")
    c, f = entry(t["by_verdict"], "continue"), entry(t["by_verdict"], "fade")
    assert (c["label"], c["n"], c["hit"], c["base_hit"]) == ("үргэлжлэх", 30, 0.6, 0.32)
    assert (f["label"], f["n"], f["hit"], f["base_hit"]) == ("унтрах", 70, 0.8, 0.68)
    assert t["anomaly_base"]["n"] == 100


def test_population_is_measurable_without_group_v_and_with_a_known_outcome():
    d = pd.concat([rows(20), rows(7, measurable=False), rows(8, group="в"), rows(9, actual_pct_h3=np.nan)],
                  ignore_index=True)
    assert situation.track_record(d, "recomputed")["base"]["n"] == 20


def test_track_record_carries_source_model_version_and_period():
    d = pd.concat([rows(20), rows(20, asof=pd.Timestamp("2026-05-03"))], ignore_index=True)
    t = situation.track_record(d, "stored")
    assert (t["source_key"], t["source"]) == ("stored", "хадгалсан")
    assert (t["model_hash"], t["model_version"]) == (H, "vaaaaaaa")
    assert (t["from"], t["through"], t["days"]) == ("2026-05-01", "2026-05-03", 2)
    assert situation.track_record(d, "recomputed")["source"] == "сэргээж тооцсон"


def test_two_model_versions_are_never_mixed_into_one_number():
    d = pd.concat([rows(20), rows(20, model_hash="b" * 64)], ignore_index=True)
    with pytest.raises(ValueError, match="хувилбар"):
        situation.track_record(d, "recomputed")


# ---------------------------------------------------------------- "бүгд унтрах" өдөр (ADR 0021: valid дээр 8/271)

def test_all_fade_day_keeps_its_anomalies_and_says_all_fade():
    """2025-11-16 (valid): as-of replay-д "үргэлжлэх" 0. Нүүр хоосон болохгүй: anomaly-ууд бүгд "унтрах" дүгнэлттэй
    хэвээр, өдрийн хураангуй all_fade."""
    from src import backtest, live, serve, train
    d = pd.Timestamp("2025-11-16")
    raw = live.RawCache.load(ROOT / "data" / "processed")
    snap = serve.Snapshot.from_raw(backtest.truncate(raw, d))
    res = serve.trending(train.load(), snap, d + pd.Timedelta(days=1))
    an = [t for t in res["items"] if t["anomaly"] and t["pct"] is not None]
    assert len(an) == 19 and all(t["verdict"] == "fade" and t["verdict_label"] == "унтрах" for t in an)
    assert res["anomalies"] == {"n": 19, "continue": 0, "fade": 19, "all_fade": True}
