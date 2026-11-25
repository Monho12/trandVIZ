"""src/anomaly.py: Anomaly = анхаарал дээрх robust z ≥ 3, ▲ ×N анхаарал дээр, ердийн өдрийн уншилт (ADR 0017).  pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import anomaly  # noqa: E402

T = pd.Timestamp("2026-11-09")       # asof
TOTAL = 1_000_000_000                # нийт уншилт = 1 тэрбум тул уншилт = анхаарал × 1000


def frame(y_by_age: dict[int, float], days: int = 60, default: float = 1.0, article: str = "A") -> pd.DataFrame:
    """Нэг сэдвийн t−(days−1) … t өдрийн цуваа. y_by_age: {k: y} нь t−k өдрийн y = log1p(анхаарал)."""
    dates = pd.date_range(T - pd.Timedelta(days=days - 1), T)
    age = (T - dates).days
    y = np.array([y_by_age.get(int(k), default) for k in age], dtype=float)
    x = np.expm1(y)
    return pd.DataFrame({"article": article, "date": dates, "views": np.round(x * TOTAL / 1e6).astype("int64"),
                         "total_views": TOTAL, "attention": x, "y": y})


def cycle_window(values=(0.8, 1.0, 1.2)) -> dict[int, float]:
    """t−59 … t−7 өдрүүдэд 0.8, 1.0, 1.2 ээлжилнэ: медиан 1.0, MAD 0.2 (35 цэг 0.2-оор, 18 нь 0-ээр зөрнө)."""
    return {k: values[k % 3] for k in range(7, 60)}


def at_t(df: pd.DataFrame) -> pd.Series:
    s = anomaly.score(df)
    return s[df["date"].to_numpy() == T].iloc[0]


def test_z_is_robust_z_of_log_attention_against_days_t59_to_t7():
    """z = (y_t − медиан) / (1.4826·MAD): медиан 1.0, MAD 0.2 -> y_t = 2.0 бол z = 1.0 / 0.29652 = 3.372.
    t−6 … t−1-ийн огцом өсөлт (y = 5) цонхонд орохгүй."""
    y = {**cycle_window(), **{k: 5.0 for k in range(1, 7)}, 0: 2.0}
    assert at_t(frame(y))["z"] == pytest.approx(3.372, abs=1e-3)


@pytest.mark.parametrize("y_t,want", [(1.0 + 3 * 0.29652 + 1e-6, True), (1.0 + 3 * 0.29652 - 1e-3, False)])
def test_anomaly_iff_z_at_least_3(y_t, want):
    r = at_t(frame({**cycle_window(), 0: y_t}))
    assert bool(r["anomaly"]) is want


def test_flat_window_uses_mad_floor_005():
    """Цонх бүхэлдээ 1.0 (MAD = 0): σ̂ = 1.4826 · 0.05 = 0.0741 -> y_t = 1.2 бол z = 2.70 (inf биш)."""
    assert at_t(frame({0: 1.2}))["z"] == pytest.approx(2.698, abs=1e-3)


def test_fewer_than_28_points_in_window_gives_no_z_and_no_anomaly():
    """Түүх 34 өдөр: цонх t−33 … t−7 = 27 цэг -> z тодорхойгүй, anomaly биш. 35 өдөр (28 цэг) бол z бий."""
    short = at_t(frame({0: 9.0}, days=34))
    assert np.isnan(short["z"]) and not short["anomaly"]
    assert np.isfinite(at_t(frame({0: 9.0}, days=35))["z"])


def test_scores_up_to_t_do_not_depend_on_days_after_t():
    """t хүртэлх мөр бүрийн тоо t-ээс хойших өгөгдлөөс хамаарахгүй (acceptance: зөвхөн t−7-оос өмнөх цонх + t өдөр)."""
    base = frame({**cycle_window(), 0: 2.0}, days=120)
    later = pd.DataFrame({"article": "A", "date": pd.date_range(T + pd.Timedelta(days=1), periods=10),
                          "views": 10 ** 6, "total_views": TOTAL, "attention": 1e6, "y": np.log1p(1e6)})
    with_future = pd.concat([base, later], ignore_index=True)
    a, b = anomaly.score(base), anomaly.score(with_future).iloc[:len(base)]
    pd.testing.assert_frame_equal(a, b)


def test_ratio_is_on_attention_and_raw_views_ratio_and_normal_come_from_views():
    """Цонхны анхаарал expm1(0.8/1.0/1.2) = 1.226/1.718/2.320, уншилт 1226/1718/2320 (медиан 1718).
    t өдөр y = 2.0 (анхаарал 6.389), харин нийт уншилт 2 дахин их тул уншилт 12 778.
    ×N = 6.389 / 1.718 = e + 1 = 3.718 (анхаарал), уншилтын ×N = 12 778 / 1718 = 7.438, ердийн өдөр = 1718 уншилт."""
    df = frame({**cycle_window(), 0: 2.0})
    t = df["date"] == T
    df.loc[t, "total_views"] = 2 * TOTAL
    df.loc[t, "views"] = 12_778
    r = at_t(df)
    assert r["ratio"] == pytest.approx(3.718, abs=1e-3)
    assert r["views_ratio"] == pytest.approx(7.438, abs=1e-3)
    assert r["normal"] == 1718


def test_typical_swing_is_expm1_of_sigma():
    """Ердийн хэлбэлзэл = expm1(1.4826 · max(MAD, 0.05)): MAD 0.2 -> ±35%, тогтвортой (MAD floor) -> ±8% (ADR 0017-ийн жишээ)."""
    assert at_t(frame({**cycle_window(), 0: 2.0}))["typical_pct"] == pytest.approx(0.345, abs=1e-3)
    assert at_t(frame({0: 1.2}))["typical_pct"] == pytest.approx(0.077, abs=1e-3)


@pytest.mark.parametrize("y_t,want", [(1.1, 18), (1.2, 18), (1.21, 0), (2.0, 0)])
def test_similar_days_counts_window_days_at_least_as_high_as_t(y_t, want):
    """"Сүүлийн 2 сард ийм өдөр хэдэн удаа": t−59 … t−1-д y ≥ y_t өдрийн тоо. t−59 … t−7-д 1.2 нь 18 удаа (k = 8, 11, …, 59),
    t−6 … t−1 нь 1.0."""
    assert at_t(frame({**cycle_window(), 0: y_t}))["similar_days"] == want


def test_similar_days_includes_the_last_week_unlike_z():
    """Огцом өсөлт 3 өдрийн өмнө эхэлсэн бол (t−3 … t−1 нь y = 5) "ийм өдөр нэг ч удаа гараагүй" гэвэл худал: 3 удаа.
    z нь сүүлийн 7 хоноггүй цонхоор хэвээр (3.372)."""
    r = at_t(frame({**cycle_window(), 1: 5.0, 2: 5.0, 3: 5.0, 0: 2.0}))
    assert r["similar_days"] == 3
    assert r["z"] == pytest.approx(3.372, abs=1e-3)


def totals(t_value: float, values=(0.98, 1.0, 1.02), base: float = 2e8) -> pd.DataFrame:
    """t−59 … t−1 өдрийн нийт уншилт base × 0.98/1.0/1.02 ээлжилнэ (log MAD 0.0198, σ̂ 0.0294), t өдөр base × t_value."""
    dates = pd.date_range(T - pd.Timedelta(days=59), T)
    v = [base * (t_value if d == T else values[(T - d).days % 3]) for d in dates]
    return pd.DataFrame({"date": dates, "total_views": np.round(v).astype("int64")})


@pytest.mark.parametrize("t_value,text", [
    (1.13, "Энэ өдөр Wikipedia-ийн нийт уншилт ердийнхөөс 13% их байсан."),     # z = +4.2
    (0.88, "Энэ өдөр Wikipedia-ийн нийт уншилт ердийнхөөс 12% бага байсан."),   # z = −4.4
])
def test_total_views_note_when_total_z_is_at_least_4_either_way(t_value, text):
    """Нийт уншилтын z = log(нийт) дээр, ижил цонх, MAD floor-гүй (нийт уншилт ±3%-иар л хэлбэлздэг). |z| ≥ 4 бол мөр нэмнэ."""
    note = anomaly.total_note(totals(t_value), T)
    assert note["text"] == text
    assert note["pct"] == pytest.approx(t_value - 1, abs=1e-6)
    assert abs(note["z"]) >= 4


def test_no_total_views_note_on_an_ordinary_day():
    assert anomaly.total_note(totals(1.10), T) is None       # z = +3.2
    assert anomaly.total_note(totals(1.0), T) is None


# ---------------------------------------------------------------- data/processed дээр ADR 0017-ийн тоо

@pytest.fixture(scope="module")
def processed():
    """Image-ийн data/processed-ийн бүтэн цэвэр түүх (сургалт, сервертэй ижил clean_frame) ба нийт уншилт."""
    from src import live, serve
    raw = live.RawCache.load(Path(__file__).resolve().parents[1] / "data" / "processed")
    return pd.concat(list(serve.clean_chunks(raw)), ignore_index=True), raw.total


def test_valid_anomalies_per_day_and_weekday_spread_match_adr_0017(processed):
    """(в)-гүй valid (purge-ийн 3 өдрийг хассан 271 өдөр), хэмжигдэх сэдэв: өдөрт ~19.6 anomaly, гарагаар max/min ≈ 1.08."""
    from src import features, scoring, train
    cl, _ = processed
    cl = cl.assign(measurable=scoring.is_measurable(cl[["article", "date", "y"]]).to_numpy(),
                   anomaly=anomaly.score(cl)["anomaly"].to_numpy())
    va = cl[(cl["date"] > features.TRAIN_END) & (cl["date"] <= features.VALID_END - pd.Timedelta(days=max(features.HORIZONS)))]
    va = va[va["measurable"] & (va["article"].astype(str).map(train.load_groups()) != scoring.GROUP_NEW_VIRAL)]
    per_day = va.groupby("date")["anomaly"].sum()
    assert len(per_day) == 271
    assert per_day.mean() == pytest.approx(19.6, abs=0.05)
    by_dow = per_day.groupby(per_day.index.dayofweek).mean()
    assert by_dow.max() / by_dow.min() == pytest.approx(1.08, abs=0.005)


@pytest.mark.parametrize("day,text", [
    ("2024-11-06", "13% их"), ("2022-09-08", "18% их"), ("2022-09-09", "18% их"), ("2024-05-31", "10% бага"),
])
def test_total_views_note_appears_on_adr_0017_unusual_days(processed, day, text):
    _, total = processed
    assert text in anomaly.total_note(total, pd.Timestamp(day))["text"]


def test_total_views_note_days_are_exactly_the_ten_in_adr_0017(processed):
    """ADR 0017: 2021-06 … 2026-11-д |z_нийт| ≥ 4 өдөр 10."""
    _, total = processed
    days = [d for d in total["date"] if anomaly.total_note(total, d) is not None]
    assert len(days) == 10
