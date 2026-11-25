"""src/cycle.py: Мөчлөг, Илүүдэл, Мөчлөгийн өсөлт/бууралт, Давж өсөх жагсаалт (ADR 0019).  pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import cycle  # noqa: E402

T = pd.Timestamp("2026-11-09")       # asof (Даваа)


def frame(x_by_age: dict[int, float], days: int = 35, default: float = 10.0, article: str = "A") -> pd.DataFrame:
    """Нэг сэдвийн t−(days−1) … t өдрийн анхаарал. x_by_age: {k: x} нь t−k өдрийн анхаарал."""
    dates = pd.date_range(T - pd.Timedelta(days=days - 1), T)
    x = [x_by_age.get(int(k), default) for k in (T - dates).days]
    return pd.DataFrame({"article": article, "date": dates, "attention": np.array(x, dtype=float)})


def transitions(ratios) -> dict[int, float]:
    """Сүүлийн 4 долоо хоногийн ижил гарагийн шилжилт: t−7k өдөр 10, t−7k+3 өдөр 10 × ratios[k−1] (k = 1…4)."""
    return {7 * k - 3: 10.0 * r for k, r in enumerate(ratios, start=1)}


def at_t(df: pd.DataFrame) -> float:
    return float(cycle.cycle(df)[(df["date"] == T).to_numpy()].iloc[0])


def test_cycle_is_median_of_last_4_same_weekday_transitions_minus_1():
    """asof гараг → asof+3 гараг: t−7 → t−4, t−14 → t−11, t−21 → t−18, t−28 → t−25.
    Харьцаа 1.1, 2.0, 1.2, 1.5 -> медиан (1.2 + 1.5) / 2 = 1.35 -> мөчлөг +35%."""
    assert at_t(frame(transitions([1.1, 2.0, 1.2, 1.5]))) == pytest.approx(0.35)


def test_cycle_needs_28_days_of_history_before_asof():
    """t−28 өдөр байхгүй бол (29 өдрийн түүх: t−28 … t, 28-аас цөөн бол) мөчлөг тодорхойгүй."""
    assert np.isfinite(at_t(frame(transitions([1.1, 2.0, 1.2, 1.5]), days=29)))
    assert np.isnan(at_t(frame(transitions([1.1, 2.0, 1.2, 1.5]), days=28)))


def test_cycle_is_undefined_when_a_transition_starts_from_zero_attention():
    assert np.isnan(at_t(frame({**transitions([1.1, 2.0, 1.2, 1.5]), 14: 0.0})))


def test_cycle_at_t_does_not_depend_on_days_after_t_or_t_minus_3_to_t():
    """Мөчлөг нь t−28 … t−4-өөс л гарна: t−3 … t болон t-ээс хойших өдрийг өөрчилсөн ч ижил."""
    base = frame(transitions([1.1, 2.0, 1.2, 1.5]))
    noisy = frame({**transitions([1.1, 2.0, 1.2, 1.5]), 0: 999.0, 1: 0.0, 2: 5.0, 3: 77.0})
    later = pd.DataFrame({"article": "A", "date": pd.date_range(T + pd.Timedelta(days=1), periods=5), "attention": 1e6})
    assert at_t(noisy) == at_t(base) == at_t(pd.concat([base, later], ignore_index=True))


def test_cycle_is_computed_per_topic():
    a = frame(transitions([1.1, 2.0, 1.2, 1.5]), article="A")
    b = frame(transitions([0.5, 0.5, 0.6, 0.9]), article="B")
    both = pd.concat([b, a], ignore_index=True)        # эрэмбэгүй залгасан
    c = cycle.cycle(both)[(both["date"] == T).to_numpy()]
    assert dict(zip(both.loc[c.index, "article"], c.round(6))) == {"A": 0.35, "B": -0.45}


def test_excess_is_ratio_of_growth_to_cycle_growth():
    """CONTEXT.md-ийн жишээ: мөчлөг +12%, таамаг +40% -> илүүдэл 1.40 / 1.12 − 1 = +25%."""
    assert cycle.excess(0.40, 0.12) == pytest.approx(0.25)
    assert cycle.excess(0.15, 0.30) == pytest.approx(1.15 / 1.30 - 1)       # −11.5%: мөчлөгөөсөө бага өснө


@pytest.mark.parametrize("cyc,pred,want", [
    (0.30, 0.15, True),     # мөчлөгөөсөө БАГА өсөх Rising (e = −11.5%): нэг талын дүрмээр мөчлөгийн өсөлт
    (0.12, 0.40, False),    # мөчлөгөөс эрс давсан (e = +25%): жирийн Rising
    (0.10, 0.20, True),     # мөчлөг яг +10%, e = +9.1% < +10%
    (0.09, 0.15, False),    # мөчлөг +10%-иас бага: мөчлөггүй
    (0.30, 0.05, False),    # Rising биш (таамаг < +10%)
    (np.nan, 0.40, False),  # мөчлөг тодорхойгүй
])
def test_cyclical_rise_is_one_sided(cyc, pred, want):
    """Мөчлөгийн өсөлт ⇔ Rising (таамаг ≥ +10%), мөчлөг ≥ +10% ба e < +10% (ADR 0019)."""
    assert bool(cycle.is_cyclical_rise(pred, cyc)) is want


@pytest.mark.parametrize("cyc,pred,want", [
    (-0.30, -0.15, True),   # мөчлөгөөсөө бага буурах Declining (e = +21%)
    (-0.12, -0.40, False),  # мөчлөгөөс эрс илүү буурна (e = −32%)
    (-0.30, -0.05, False),  # Declining биш
    (-0.05, -0.20, False),  # мөчлөг −10%-иас бага
])
def test_cyclical_fall_mirrors_the_rise_rule(cyc, pred, want):
    """Мөчлөгийн бууралт ⇔ Declining (таамаг ≤ −10%), мөчлөг ≤ −10% ба e > −10%."""
    assert bool(cycle.is_cyclical_fall(pred, cyc)) is want


def day(rows, date=T) -> pd.DataFrame:
    """rows: [(article, pred_pct, cycle, measurable)] нэг өдрийн."""
    return pd.DataFrame([{"date": date, "article": a, "pred_pct": p, "cycle": c, "measurable": m} for a, p, c, m in rows])


def test_beyond_list_excludes_rise_below_its_cycle_and_keeps_rise_far_above_it():
    """Acceptance (#49): мөчлөг +30%, таамаг +15% байгаа сэдэв жагсаалтад ОРОХГҮЙ; мөчлөг +12%, таамаг +40% ОРНО."""
    got = cycle.beyond_list(day([("below_cycle", 0.15, 0.30, True), ("above_cycle", 0.40, 0.12, True)]))
    assert got["article"].tolist() == ["above_cycle"]
    assert got["rank"].tolist() == [1]


def test_beyond_list_is_at_most_10_ranked_by_predicted_pct_and_fewer_is_fewer():
    """Rising (≥ +10%), хэмжигдэх, мөчлөгийн өсөлт биш; pct-ээр буурахаар (тэнцвэл нэрээр); дээд тал нь 10.
    Stable (+5%), хэмжигдэхгүй, мөчлөгийн өсөлтөөр нөхөхгүй."""
    many = day([(f"r{i:02d}", 0.10 + i / 100, 0.0, True) for i in range(12)])
    got = cycle.beyond_list(many)
    assert got["article"].tolist() == [f"r{i:02d}" for i in range(11, 1, -1)]
    assert got["rank"].tolist() == list(range(1, 11))
    few = day([("b", 0.30, np.nan, True), ("a", 0.30, 0.0, True), ("stable", 0.05, 0.0, True),
               ("small", 0.90, 0.0, False), ("cyclic", 0.20, 0.20, True), ("nopct", np.nan, 0.0, True)])
    assert cycle.beyond_list(few)["article"].tolist() == ["a", "b"]
    assert cycle.beyond_list(day([("stable", 0.05, 0.0, True)])).empty


def test_beyond_list_is_per_day():
    d1 = day([("x", 0.50, 0.0, True)], T)
    d2 = day([("y", 0.20, 0.0, True), ("z", 0.30, 0.0, True)], T + pd.Timedelta(days=1))
    got = cycle.beyond_list(pd.concat([d2, d1], ignore_index=True))
    assert list(zip(got["date"], got["article"], got["rank"])) == [
        (T, "x", 1), (T + pd.Timedelta(days=1), "z", 1), (T + pd.Timedelta(days=1), "y", 2)]


def test_cyclical_rise_list_is_the_measurable_cyclical_rises_ranked_by_predicted_pct():
    """Мөчлөгийн өсөлтийн тусдаа жагсаалт (W7-д хураасан "Долоо хоногийн ..." хэсэг): хэмжигдэх, pct-ээр, хязгааргүй."""
    d = day([("c1", 0.15, 0.30, True), ("c2", 0.25, 0.20, True), ("small", 0.40, 0.40, False), ("plain", 0.40, 0.12, True)])
    got = cycle.cyclical_rise_list(d)
    assert got["article"].tolist() == ["c2", "c1"] and got["rank"].tolist() == [1, 2]


# ---------------------------------------------------------------- (в)-гүй valid дээр ADR 0019-ийн тоо

@pytest.fixture(scope="module")
def valid():
    """calibrate.valid_frame ((в)-гүй valid, сургалт/калибровктой ижил мөр), хэмжигдэх мөрүүд, мөчлөг ба бодит pct (h3)-тэй.
    Image-ийн data/processed-оос санах ойд (clean.parquet, features.parquet-гүй)."""
    from src import calibrate, features, live, scoring, serve, train
    raw = live.RawCache.load(Path(__file__).resolve().parents[1] / "data" / "processed")
    cl = pd.concat(list(serve.clean_chunks(raw)), ignore_index=True)
    va = calibrate.valid_frame(train.load(), features.frame(cl), cl)
    cyc = cl[["article", "date"]].assign(cycle=cycle.cycle(cl).to_numpy())
    va = va.merge(cyc, on=["article", "date"], how="left")
    va["actual_pct"] = scoring.pct(va["y_0"], va["y_h3"])
    return va[va["measurable"].fillna(False).astype(bool)]


def test_valid_beyond_list_reproduces_adr_0019(valid):
    """ADR 0019 (valid, (в)-гүй, хэмжигдэх, 271 өдөр): бодит илүүдлийн нарийвчлал 58.9%, precision (бодит ≥ +25%) 31.1%,
    10-аас цөөн өдөр 102, 0-тэй өдөр 2, үндсэн хувь ~29%."""
    from src import evaluate
    m = evaluate.beyond_list_metrics(valid)
    assert m["days"] == 271
    assert m["excess_hit"] == pytest.approx(0.589, abs=0.0005)
    assert m["precision"] == pytest.approx(0.311, abs=0.0005)
    assert (m["days_short"], m["days_empty"]) == (102, 2)
    assert m["base_rate"] == pytest.approx(0.29, abs=0.005)


def test_old_top10_numbers_are_unchanged_on_valid(valid):
    """Хамгаалалтын precision@10 (хуучин тодорхойлолт, scoring.top10) өөрчлөгдөөгүй: valid дээр хуучин top-10-ийн
    precision 43.6% (ADR 0019-ийн хүснэгт)."""
    from src import evaluate
    p, days = evaluate.precision_at_10(valid, "pred_pct")
    assert days == 271 and p == pytest.approx(0.436, abs=0.0005)
