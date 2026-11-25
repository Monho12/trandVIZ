"""Давтамжийн тооны скрипт (#54, scripts/frequency_numbers.py): үндсэн функцүүд жижиг fixture дээр.  pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import frequency_numbers as fn  # noqa: E402

A, B, C = (pd.Timestamp(d) for d in ("2025-07-01", "2025-07-02", "2025-07-03"))


def rows(*r) -> pd.DataFrame:
    """(date, anomaly, pred_pct (h3), actual_pct (h3))."""
    return pd.DataFrame(r, columns=["date", "anomaly", "pred_pct", "actual_pct"])


# ---------------------------------------------------------------- дүгнэлт ба h3 үр дүн (#1–#5, ADR 0021)

def test_verdict_numbers_use_the_h3_prediction_for_the_verdict_and_the_h3_day_for_the_outcome():
    d = rows((A, True, -0.30, -0.50),    # унтрах, унтарсан
             (A, True, 0.05, 0.20),      # үргэлжлэх, унтраагүй
             (A, True, 0.20, 0.00),      # үргэлжлэх, унтраагүй
             (A, True, -0.10, -0.05),    # унтрах (≤ −10% хил орно), унтраагүй
             (A, False, 0.50, 0.50),     # Anomaly биш: тоонд орохгүй
             (B, True, 0.00, -0.10),     # үргэлжлэх, унтарсан (бодит ≤ −10% хил орно)
             (C, False, 0.00, 0.00))     # Anomaly-гүй өдөр: "үргэлжлэх" 0-тэй өдөрт тоологдоно
    got = fn.verdict_numbers(d)
    assert got["days"] == 3 and got["anomalies"] == 5 and got["continue"] == 3
    assert got["anomalies_per_day"] == pytest.approx(5 / 3)
    assert got["faded_share"] == pytest.approx(2 / 5)
    assert got["continue_per_day"] == pytest.approx(1.0)
    assert got["continue_share"] == pytest.approx(3 / 5)
    assert got["continue_held"] == pytest.approx(2 / 3)      # "үргэлжлэх"-ийн хэдэн % нь унтраагүй
    assert got["base_held"] == pytest.approx(3 / 5)          # бүх Anomaly-ийн хэдэн % нь унтраагүй (ердийн үед)
    assert (got["days_zero_continue"], got["days_one_continue"]) == (1, 1)


# ---------------------------------------------------------------- хүчтэй өсөлт ба мөчлөгийн өсөлтийг хасах (#6, #7, ADR 0026)

D = pd.Timestamp("2025-07-04")


def test_strong_rises_with_and_without_cyclical_rises_and_days_with_nothing_bold():
    d = pd.DataFrame([
        (A, False, 0.40, 0.30),     # хүчтэй, гэхдээ мөчлөгийн өсөлт (илүүдэл 1.4/1.3 − 1 ≈ +7.7% < +10%): тод биш
        (A, False, 0.30, 0.00),     # хүчтэй, тод
        (B, False, 0.40, np.nan),   # мөчлөг тодорхойгүй: мөчлөгийн өсөлт биш, тод
        (C, False, 0.40, 0.30),     # мөчлөгийн өсөлт: тод биш
        (C, True, -0.30, 0.00),     # Anomaly, "унтрах": тод биш -> C өдөр тод зүйлгүй
        (D, True, 0.00, 0.00),      # Anomaly, "үргэлжлэх": тод үг
        (D, False, 0.2499, 0.00),   # T-ээс доош
    ], columns=["date", "anomaly", "pred_pct", "cycle"])
    got = fn.bold_numbers(d, T=0.25)
    assert got["strong_per_day"] == pytest.approx(1.0) and got["strong_share"] == pytest.approx(4 / 7)
    assert got["bold_per_day"] == pytest.approx(0.5) and got["bold_share"] == pytest.approx(2 / 7)
    assert got["days_zero_bold_number"] == 2       # C, D
    assert got["days_nothing_bold"] == 1           # C: тод тоо ч, "үргэлжлэх" ч алга


# ---------------------------------------------------------------- үндсэн хувь (#9, #12, ADR 0019, 0020)

def test_base_rate_is_the_share_with_actual_excess_at_least_10_pct_over_rows_with_a_known_cycle():
    actual = [0.30, 0.15, 0.10, 0.50]
    cyc = [0.10, 0.10, 0.00, np.nan]     # илүүдэл +18.2% / +4.5% / +10% (хил орно) / тодорхойгүй (тоонд орохгүй)
    assert fn.excess_hit_rate(actual, cyc) == pytest.approx(2 / 3)


# ---------------------------------------------------------------- 80% интервал тэлэх эсэх (#11, ADR 0027)

def test_interval_widens_share_compares_the_pct_widths_each_row_would_draw():
    interval = {"h1": {"lo": -0.1, "hi": 0.1}, "h2": {"lo": -0.1, "hi": 0.2}, "h3": {"lo": -0.2, "hi": 0.2}}
    y0 = np.log1p(100.0)
    d = pd.DataFrame({"y_0": [y0, y0], "delta_hat_h1": [0.0, 0.5], "delta_hat_h2": [0.0, 0.0], "delta_hat_h3": [0.0, 0.0]})
    # мөр 1: Δ̂ ижил тул өргөн нь лог өргөнөөр (0.2 < 0.3 < 0.4) тэлнэ.
    # мөр 2: h1-ийн Δ̂ = +0.5 тул h1-ийн band (≈ 0.334) h2-ийнхоос (≈ 0.320) өргөн: тэлэхгүй.
    got = fn.interval_widening(d, interval)
    assert got["share_widening"] == pytest.approx(0.5)
    assert got["log_width"] == pytest.approx({"h1": 0.2, "h2": 0.3, "h3": 0.4})


# ---------------------------------------------------------------- Буцалтын naive дүрэм (#12)

def test_normal_levels_are_the_28_day_median_and_the_adr_0017_window_median():
    d = pd.DataFrame({"article": "x", "date": pd.date_range(A, periods=60), "y": np.arange(60.0)})
    got = fn.normal_levels(d).set_index(d["date"].dt.day_of_year - A.day_of_year)
    assert got.loc[59, "level_28"] == 45.5            # t−27 … t = 32 … 59
    assert np.isnan(got.loc[26, "level_28"])          # 28 хоногоос богино түүх
    assert got.loc[59, "level_0017"] == 26.0          # t−59 … t−7 = 0 … 52
    assert got.loc[34, "level_0017"] == 13.5          # 0 … 27: яг 28 цэг
    assert np.isnan(got.loc[33, "level_0017"])        # 27 цэг (< 28, ADR 0017)


def test_same_n_list_takes_each_day_as_many_non_cyclical_rising_rows_as_the_model_list_had():
    d = pd.DataFrame([
        (A, "a", 0.50, 0.00), (A, "b", 0.30, 0.00), (A, "e", 0.20, 0.00),
        (A, "c", 0.40, 0.35),     # мөчлөгийн өсөлт (илүүдэл ≈ +3.7%): орохгүй
        (A, "d", 0.05, 0.00),     # Rising биш
        (B, "a", 0.90, 0.00),     # тэр өдөр model-ийн жагсаалт 0
        (C, "a", 0.30, 0.00), (C, "b", 0.00, 0.00),
    ], columns=["date", "article", "naive_pct", "cycle"])
    got = fn.same_n_list(d, "naive_pct", pd.Series({A: 2, C: 3}))
    assert list(zip(got["date"], got["article"])) == [(A, "a"), (A, "b"), (C, "a")]


# ---------------------------------------------------------------- AUC (ADR 0021: "унтрах" эрэмбэ 0.744, z ганцаараа 0.591)

def test_auc_is_the_probability_a_positive_outranks_a_negative_with_ties_counting_half():
    assert fn.auc([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1]) == pytest.approx(0.75)
    assert fn.auc([1.0, 1.0], [0, 1]) == pytest.approx(0.5)


# ---------------------------------------------------------------- "Өгөгдөл дутуу"-гийн босго (#13, #14, ADR 0016, 0022)

def test_total_ratio_is_the_day_over_the_median_of_the_previous_28_days_like_the_server_check():
    t = pd.DataFrame({"date": pd.date_range(A, periods=30), "total_views": [100.0] * 28 + [90.0, 120.0]})
    got = fn.total_ratio(t)
    assert got.index.tolist() == list(pd.date_range(A, periods=30)[28:])   # эхний 28 өдөрт суурь бүрэн биш
    assert got.tolist() == pytest.approx([0.9, 1.2])                       # 30 дахь өдрийн суурь 90-ийг орно: медиан 100


def test_article_coverage_counts_topics_with_views_against_all_rows_of_the_previous_day_like_the_server():
    """Сервер: шинэ өдрийн API мөр (0 уншилтыг буцаадаггүй) ÷ cache-ийн сүүлийн өдрийн мөр (0 уншилттай мөр ч орно)."""
    pv = pd.DataFrame([(A, "a", 5), (A, "b", 3), (A, "c", 1), (A, "d", 2),
                       (B, "a", 4), (B, "b", 0), (B, "c", 2), (B, "d", 1),    # 0 уншилт = API мөр буцаагаагүй
                       (C, "a", 1), (C, "b", 1), (C, "c", 1), (C, "d", 1)], columns=["date", "article", "views"])
    assert fn.article_coverage(pv).tolist() == pytest.approx([0.75, 1.0])


def test_share_threshold_is_the_largest_step_strictly_below_every_complete_day():
    assert fn.share_threshold([0.886, 1.1, 0.95]) == pytest.approx(0.85)
    assert fn.share_threshold([0.90, 1.0]) == pytest.approx(0.85)       # 0.90 өдөр "> босго"-оор давах ёстой
    assert fn.share_threshold([0.9798, 1.0]) == pytest.approx(0.95)


def test_partial_day_flips_count_anomaly_flags_that_change_when_one_day_is_x_pct_short():
    y = np.log1p(100.0)
    d = pd.DataFrame({"date": [A, A, B], "attention": [100.0, 100.0, 100.0], "y_0": [y, y, y],
                      "z": [2.9, 3.2, 0.0], "sigma": [0.1, 0.1, 0.1], "anomaly": [False, True, False]})
    # X = 5%: y-ийн шилжилт ±log(106/101) ≈ ±0.048 -> z ±0.48. Сэдвийн уншилт дутуу (анхаарал ↓) бол 3.2 нь 2.72 болж унана,
    # нийт уншилт дутуу (анхаарал ↑) бол 2.9 нь 3.38 болж Anomaly болно. 2 өдөр тул өдөрт 0.5.
    assert fn.partial_day_flips(d, 0.05) == pytest.approx({"down": 0.5, "up": 0.5})
    assert fn.partial_day_flips(d, 0.01) == pytest.approx({"down": 0.0, "up": 0.0})   # z ±0.098: хил давахгүй


def test_tolerated_shortfall_is_the_largest_x_whose_worse_direction_stays_within_the_limit():
    flips = {0.005: {"down": 0.2, "up": 0.3}, 0.01: {"down": 0.5, "up": 0.9}, 0.015: {"down": 0.8, "up": 1.1}}
    assert fn.tolerated_shortfall(flips, max_flips=1.0) == 0.01
    assert fn.tolerated_shortfall(flips, max_flips=0.1) is None


def test_day_bootstrap_diff_resamples_days_and_pools_hits_within_each_list():
    a = pd.DataFrame({"date": [A, A, B, C], "hit": [True, True, True, False]})
    same = fn.day_bootstrap_diff(a, a, n=200)
    assert same["diff"] == 0 and same["lo"] == 0 and same["hi"] == 0
    b = a.assign(hit=False)
    got = fn.day_bootstrap_diff(a, b, n=200)
    assert got["diff"] == pytest.approx(0.75) and 0 <= got["lo"] <= 0.75 <= got["hi"] <= 1
    assert fn.day_bootstrap_diff(a, b, n=200) == got     # тогтмол seed: дахин ажиллуулахад ижил


# ---------------------------------------------------------------- бүтэн ажиллуулалт: commit хийсэн тайлан кодтой ба ADR-тай таарна

def _approx_equal(a, b, path=""):
    if isinstance(a, dict):
        assert set(a) == set(b), path
        for k in a:
            _approx_equal(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _approx_equal(x, y, f"{path}[{i}]")
    elif isinstance(a, float) and not isinstance(b, bool):
        assert b == pytest.approx(a, abs=2e-6), path
    else:
        assert a == b, path


def test_committed_report_is_reproduced_and_every_documented_number_matches():
    """docs/numbers/frequency.json = data/processed + app/model-оос дахин гаргасан тайлан. Зөрвөл: өгөгдөл/model өөрчлөгдсөн
    бол `python scripts/frequency_numbers.py`-г дахин ажиллуулж, ADR-ийн тоог шинэчил (scripts/frequency_numbers.CLAIMS)."""
    import json

    got = fn.report(fn.load())
    committed = json.loads((ROOT / "docs" / "numbers" / "frequency.json").read_text(encoding="utf-8"))
    _approx_equal(committed, json.loads(json.dumps(got)))
    assert [c for c in got["claims"] if not c["matches"]] == []
    assert (ROOT / "docs" / "numbers" / "frequency.md").read_text(encoding="utf-8") == fn.render_md(got)
