"""src/evaluate.py: test-ийн нэг удаагийн үнэлгээний хэмжүүрүүд (ADR 0002, 0005).
Хүлээгдэх утгууд нь гараар тооцсон жижиг жишээнүүд.  Ажиллуулах:  pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import evaluate, scoring  # noqa: E402


def days(*per_day):
    """[(date, [(err_model, err_naive), ...]), ...] -> [date, err_model, err_naive]."""
    return pd.DataFrame([{"date": pd.Timestamp(d), "err_model": m, "err_naive": n}
                         for d, rows in per_day for m, n in rows])


def test_skill_ci_collapses_when_every_day_is_identical():
    # Өдөр бүр skill = 1 − 2/4 = 50% -> аль ч resample 50%
    df = days(("2026-04-01", [(1, 2), (1, 2)]), ("2026-04-02", [(1, 2), (1, 2)]))
    point, lo, hi = evaluate.skill_ci(df, n_boot=200, seed=0)
    assert (point, lo, hi) == pytest.approx((0.5, 0.5, 0.5))


def test_skill_ci_resamples_days_not_rows():
    # A өдөр: 100 мөр, model = naive (skill 0). B өдөр: 1 мөр, model 0 алдаатай.
    # Өдрөөр resample: AA -> 0, AB -> 1/101, BB -> 1 (25%) тул 97.5%-ийн хил = 1.
    # Мөрөөр resample хийсэн бол дээд хил ~0.03 орчим л гарна.
    df = days(("2026-04-01", [(1, 1)] * 100), ("2026-04-02", [(0, 1)]))
    point, lo, hi = evaluate.skill_ci(df, n_boot=2000, seed=0)
    assert point == pytest.approx(1 / 101)
    assert lo == pytest.approx(0.0)
    assert hi == pytest.approx(1.0)


def ranking_frame():
    """2 өдөр × 11 хэмжигдэх сэдэв (a00 нь хамгийн өндөр таамагтай) + хэмжигдэхгүй "z" (таамаг 99, бодитоор ↑).
    1-р өдөр a00, a01, a02 ба 11-р байрны a10 нь ↑; 2-р өдөр зөвхөн a00. 3-р өдөр 5-хан хэмжигдэх сэдэвтэй."""
    rows = []
    for d, ups, n in (("2026-04-01", {"a00", "a01", "a02", "a10"}, 11), ("2026-04-02", {"a00"}, 11),
                      ("2026-04-03", {"a00"}, 5)):
        for i in range(n):
            a = f"a{i:02d}"
            rows.append({"date": pd.Timestamp(d), "article": a, "measurable": True, "pred_pct": 10.0 - i,
                         "actual_pct": 0.5 if a in ups else 0.0})
        rows.append({"date": pd.Timestamp(d), "article": "z", "measurable": False, "pred_pct": 99.0, "actual_pct": 0.5})
    return pd.DataFrame(rows)


def test_precision_at_10_is_daily_mean_over_measurable_top10():
    # 1-р өдөр 3/10, 2-р өдөр 1/10 -> 20%. "z" хэмжигдэхгүй, a10 нь 11-р байр. 3-р өдөр (5 сэдэв) тоологдохгүй.
    p, n_days = evaluate.precision_at_10(ranking_frame(), "pred_pct")
    assert p == pytest.approx(0.2)
    assert n_days == 2


def test_base_rate_is_daily_share_of_up_among_measurable():
    # 1-р өдөр 4/11, 2-р өдөр 1/11 (precision@10-тэй ижил өдрүүд) -> 5/22
    assert evaluate.base_rate(ranking_frame()) == pytest.approx(5 / 22)


def test_direction_accuracy_counts_rise_and_fall_separately():
    # ӨСӨХ (≥ +25%): +1 ✓, −1 ✗, 0 ✗ -> 1/3.  БУУРАХ (≤ −20%): −1 ✓, +1 ✗ -> 1/2.  Тогтвортой (0%) тоологдохгүй.
    actual = pd.Series([0.30, 0.50, 0.25, -0.20, -0.50, 0.0])
    pred_dir = pd.Series([1, -1, 0, -1, 1, 1])
    got = evaluate.direction_accuracy(actual, pred_dir)
    assert got == pytest.approx({"rise": 1 / 3, "fall": 0.5, "n_rise": 3, "n_fall": 2})


def test_share_days_better_compares_daily_mae_strictly():
    # 1-р өдөр загвар сайн, 2-р өдөр тэнцүү (тоологдохгүй), 3-р өдөр муу -> 1/3. Өдрийн MAE нь мөрийн дундаж.
    df = days(("2026-04-01", [(1, 2), (1, 2)]), ("2026-04-02", [(1, 1)]), ("2026-04-03", [(0, 1), (6, 1)]))
    assert evaluate.share_days_better(df) == pytest.approx(1 / 3)


def test_interval_coverage_includes_bounds():
    # Δ̂ = 0, интервал [−0.1, +0.2]: −0.1 ✓, 0 ✓, 0.2 ✓, 0.21 ✗, −0.2 ✗ -> 60%
    delta = pd.Series([-0.1, 0.0, 0.2, 0.21, -0.2])
    assert evaluate.interval_coverage(delta, pd.Series(0.0, index=delta.index), -0.1, 0.2) == pytest.approx(0.6)


def metrics(skills, p_model=0.3, p_mom=0.2, rise_model=0.5, rise_mom=0.4):
    return {"skill": {f"h{h}": {"point": p, "lo": lo, "hi": 0.5} for h, (p, lo) in enumerate(skills, 1)},
            "precision10": {"model": p_model, "momentum": p_mom},
            "direction": {"model": {"rise": rise_model}, "momentum": {"rise": rise_mom}}}


def test_verdict_passes_only_when_every_adr_0002_criterion_holds():
    v = evaluate.verdict(metrics([(0.05, 0.001), (0.08, 0.02), (0.10, 0.05)]))
    assert v == {"skill": {"h1": True, "h2": True, "h3": True}, "skill_all": True,
                 "precision10": True, "rise_direction": True, "pass": True}


def test_verdict_fails_on_ci_crossing_zero_small_skill_or_ties_with_momentum():
    # h2: CI доод хил < 0;  h3: цэгэн 4.9% < 5%;  precision@10 ба ӨСӨХ momentum-тай ТЭНЦҮҮ = давсангүй
    v = evaluate.verdict(metrics([(0.06, 0.01), (0.06, -0.01), (0.049, 0.02)], p_model=0.2, rise_model=0.4))
    assert v == {"skill": {"h1": True, "h2": False, "h3": False}, "skill_all": False,
                 "precision10": False, "rise_direction": False, "pass": False}


def test_model_page_shows_group_a_mae_as_percent_and_marks_winner():
    # exp(0.1398) − 1 = 15.0%,  exp(0.1) − 1 = 10.5%
    mae = {"lightgbm": 0.1, "xgboost": 0.1, "catboost": 0.1398, "naive": 0.2, "seasonal": 0.3, "model": 0.1398}
    meta = {"algo": "catboost", "best_iteration": {"h3": 5}, "importance_top10": [{"feature": "ratio_7", "share": 0.0905}],
            "learning_curve": {"h3": {"iteration": [1, 5], "train": [0.2, 0.1], "valid": [0.21, 0.12]}},
            "test": {"test_end": "2026-11-06", "groups": {
                "а": {"mae": {"h1": mae}, "skill": {"h1": {"point": 0.301, "lo": 0.25, "hi": 0.35}}},
                "б": {"mae": {"h1": {k: 9.0 for k in mae}}, "skill": {}}}}}
    page = evaluate.model_page(meta)
    assert page["winner"] == "catboost" and page["mock"] is False
    assert page["metrics"] == [{"h": 1, "lightgbm": 10.5, "xgboost": 10.5, "catboost": 15.0, "naive": 22.1}]
    assert page["skill"] == {"h1": {"point": 30.1, "lo": 25.0, "hi": 35.0}}
    assert page["importance"] == [{"f": "ratio_7", "gain": 9}]
    assert page["names"]["naive"] == "Одоогийнхтой адилхан" and page["names"]["model"] == "Манай model (CatBoost)"
    assert page["curve_h"] == 3 and "valid" not in page   # valid_table-гүй meta


def test_valid_comparison_uses_valid_without_new_viral_and_selection_mean():
    # exp(0.1) − 1 = 10.52%, exp(0.2) − 1 = 22.14%
    vt = [{"algo": a, "h": h, "valid_mae": m, "naive_valid_mae": 0.2, "trials": 25}
          for a, m in (("lightgbm", 0.1), ("catboost", 0.1)) for h in (1, 2)]
    v = evaluate.valid_comparison({"valid_table": vt, "optuna": {"n_trials": 25}})
    assert v["algos"] == ["lightgbm", "catboost"] and v["trials"] == 100 and v["horizons"] == 2
    assert v["rows"][0] == {"h": 1, "lightgbm": 10.52, "catboost": 10.52, "naive": 22.14}
    assert v["mean"]["naive"] == 22.14 and v["mean_log"] == {"lightgbm": 0.1, "catboost": 0.1}


def test_naive_mae_by_period_purges_split_boundary():
    import pandas as pd
    from src import features
    # Train-ийн сүүлийн 3 өдөр: t+3 нь valid -> хасагдана. y нь train-д 0,1,0,1…, valid-д тогтмол.
    d = pd.date_range(features.TRAIN_END - pd.Timedelta(days=9), features.TRAIN_END + pd.Timedelta(days=10))
    y = [float(i % 2) if t <= features.TRAIN_END else 5.0 for i, t in enumerate(d)]
    out = evaluate.naive_mae_by_period(pd.DataFrame({"date": d, "article": "A", "y": y}), 3, d[0])
    assert out == {"train": 1.0, "valid": 0.0}
