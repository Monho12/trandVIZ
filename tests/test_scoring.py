"""ADR 0001/0002/0003/0004/0005-ын дүрмүүд (src/scoring.py) зөв ажиллаж байгааг шалгах жижиг тестүүд.
Хүлээгдэх утгууд нь ADR / CONTEXT.md-ийн жишээ, гараар тооцсон тооноос авагдсан.  Ажиллуулах:  pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import scoring  # noqa: E402


def test_predicted_pct_uses_x_scale_not_exp_delta():
    # ADR 0003: x_0 = 0.5, Δ̂ = 0.22 -> +74% (exp(0.22) − 1 = +25% биш)
    y_0 = np.log1p(0.5)
    assert scoring.predicted_pct(y_0, 0.22) == pytest.approx(0.74, abs=0.005)


def test_actual_pct_is_x_ratio():
    # x_0 = 2, x_h = 3 -> +50%;  x_0 = 4, x_h = 1 -> −75%
    got = scoring.pct(np.log1p([2.0, 4.0]), np.log1p([3.0, 1.0]))
    assert got == pytest.approx([0.5, -0.75])


def test_interval_bounds_converted_like_point():
    # 80% интервал: Δ квантил [0, 0.22] нь x_0 = 0.5 үед [0%, +74%] болно (exp(Δ) − 1 = [0%, +25%] биш)
    y_0 = pd.Series([np.log1p(0.5)] * 2)
    lo_hi = scoring.predicted_pct(y_0, pd.Series([0.0, 0.22]))
    assert lo_hi.tolist() == pytest.approx([0.0, 0.74], abs=0.005)


def test_true_trend_boundaries():
    # ADR 0001: бодит pct(h3) ≥ +25% ↑, ≤ −20% ↓, бусад нь тогтвортой (хил нь өөрөө ↑/↓-д орно)
    got = scoring.true_trend(pd.Series([0.25, 0.2499, -0.1999, -0.20, 3.0, np.nan]))
    assert got.tolist() == [scoring.UP, scoring.STABLE, scoring.STABLE, scoring.DOWN, scoring.UP, None]


def test_fire_threshold_never_below_25pct():
    assert scoring.fire_threshold(0.10) == 0.25
    assert scoring.fire_threshold(0.40) == 0.40


def test_arrow_boundaries_with_tuned_T():
    # ADR 0004 хүснэгт, T = 40%: ≥ T 🔥; +10%…T ↗; ±10% ≈; −10…−20% ↘; ≤ −20% ↓
    p = pd.Series([0.40, 0.3999, 0.10, 0.0999, -0.0999, -0.10, -0.1999, -0.20, -0.9, np.nan])
    got = scoring.arrow(p, tuned_T=0.40, measurable=pd.Series(True, index=p.index))
    assert got.tolist() == ["🔥", "↗", "↗", "≈", "≈", "↘", "↘", "↓", "↓", None]


def test_unmeasurable_topic_never_gets_fire():
    # Хэмжигдэхгүй сэдэв +500% таамагтай ч 🔥 авахгүй, харин ↗ (өөрийн pct-ээ харуулна)
    p = pd.Series([5.0, 5.0])
    got = scoring.arrow(p, tuned_T=0.25, measurable=pd.Series([False, True]))
    assert got.tolist() == ["↗", "🔥"]


def test_arrow_applies_T_floor_itself():
    # Тааруулсан T = 10% дамжуулсан ч +20% нь 🔥 биш (T = max(10%, 25%) = 25%)
    p = pd.Series([0.20, 0.25])
    got = scoring.arrow(p, tuned_T=0.10, measurable=pd.Series(True, index=p.index))
    assert got.tolist() == ["↗", "🔥"]


def _series(article, xs, start="2024-01-01"):
    return pd.DataFrame({"article": article, "date": pd.date_range(start, periods=len(xs)),
                         "y": np.log1p(np.asarray(xs, dtype=float))})


def test_measurable_is_7day_mean_on_x_scale():
    # A: x = 1 өдөр бүр -> 7 хоногийн дундаж x = 1 -> хэмжигдэнэ (log1p дундаж 0.69 < 1 байсан ч)
    # B: x = 0.9 -> хэмжигдэхгүй.  Эхний 6 өдөр түүх дутуу -> хэмжигдэхгүй.
    df = pd.concat([_series("B", [0.9] * 8), _series("A", [1.0] * 8)], ignore_index=True)
    got = df.assign(m=scoring.is_measurable(df)).set_index(["article", "date"])["m"]
    a = got.loc["A"]
    assert a.tolist() == [False] * 6 + [True, True]
    assert not got.loc["B"].any()


def test_measurable_uses_only_past_and_today():
    # 7-р өдрийн хувьд 1..7-р өдрийн дундаж: [0,0,0,0,0,0,7] -> 1 -> хэмжигдэнэ; 8-р өдөр асар их байх нь нөлөөлөхгүй
    df = _series("A", [0, 0, 0, 0, 0, 0, 7, 1e6])
    df2 = _series("A", [0, 0, 0, 0, 0, 0, 7, 0])
    assert scoring.is_measurable(df).iloc[6] and scoring.is_measurable(df2).iloc[6]
    assert not scoring.is_measurable(_series("A", [0, 0, 0, 0, 0, 0, 6.9])).iloc[6]


def _day(date, pcts, measurable):
    n = len(pcts)
    return pd.DataFrame({"date": pd.Timestamp(date), "article": [f"t{i:02d}" for i in range(n)],
                         "pred_pct": pcts, "measurable": measurable})


def test_top10_sorted_measurable_only_per_day():
    # Өдөр 1: 12 хэмжигдэх (pct = 0.00 … 0.11) + 1 хэмжигдэхгүй сэдэв +900% -> тэр нь орохгүй
    d1 = _day("2026-04-01", [i / 100 for i in range(12)] + [9.0], [True] * 12 + [False])
    d2 = _day("2026-04-02", [-i / 100 for i in range(11)], [True] * 11)
    top = scoring.top10(pd.concat([d2, d1], ignore_index=True), "pred_pct")
    t1 = top[top["date"] == "2026-04-01"]
    assert t1["article"].tolist() == [f"t{i:02d}" for i in range(11, 1, -1)]   # 11 … 2, буурахаар
    assert t1["rank"].tolist() == list(range(1, 11))
    assert (top.groupby("date").size() == 10).all()


def test_quiet_day_still_10_topics_and_zero_fire():
    day = _day("2026-04-01", [0.01 * (i % 3) for i in range(30)], [True] * 30)
    top = scoring.top10(day, "pred_pct")
    assert len(top) == 10
    assert (scoring.arrow(top["pred_pct"], tuned_T=0.25, measurable=top["measurable"]) != scoring.FIRE).all()


def test_top10_refuses_day_with_fewer_than_10_measurable():
    # "Үргэлж 10" дүрэм зөрчигдвөл чимээгүй 9 гаргахгүй, алдаа өгнө
    with pytest.raises(ValueError):
        scoring.top10(_day("2026-04-01", [0.5] * 12, [True] * 9 + [False] * 3), "pred_pct")


def test_topic_group_boundaries_at_2025_06_and_07():
    # ADR 0005: peak_month байхгүй (сонгосон) -> а;  ≤ 2025-06 -> б;  ≥ 2025-07 -> в
    peak = pd.Series([None, "2021-01", "2025-06", "2025-07", "2026-05"])
    assert scoring.topic_group(peak).tolist() == ["а", "б", "б", "в", "в"]


def test_viral_displayed_as_busad():
    got = scoring.display_category(pd.Series(["politics", "viral", "sport"]))
    assert got.tolist() == ["politics", "Бусад", "sport"]


def test_momentum_direction_and_pct():
    # ADR 0002: x_{−3} = 1 -> x_0 = 3: чиглэл +1, pct_m = +200%;  2 -> 2: 0, 0%;  4 -> 1: −1, −75%
    y_m3, y_0 = np.log1p([1.0, 2.0, 4.0]), np.log1p([3.0, 2.0, 1.0])
    assert scoring.momentum_direction(y_0, y_m3).tolist() == [1, 0, -1]
    assert scoring.momentum_pct(y_0, y_m3) == pytest.approx([2.0, 0.0, -0.75])


@pytest.mark.parametrize("p, text", [
    (0.74, "+75%"), (0.72, "+70%"), (0.125, "+15%"), (-0.125, "−15%"), (-0.20, "−20%"),
    (-0.02, "0%"), (0.0, "0%"), (3.0, "+300%"), (3.0001, "↑ 3×-ээс их"), (12.0, "↑ 3×-ээс их"),
])
def test_format_pct_rounds_to_5_and_caps_at_3x(p, text):
    # ADR 0003: 5%-д дугуйлна (хагас нь тэгээс холдоно, тэгш хэмтэй); +300%-иас их бол "↑ 3×-ээс их"
    assert scoring.format_pct(p) == text


def fire_frame(preds_by_day: dict, measurable=None):
    """Өдөр бүрийн таамагласан pct(h3)-ийн жагсаалтаас [date, article, pred_pct, measurable] хүснэгт."""
    rows = [{"date": pd.Timestamp(d), "article": f"a{i}", "pred_pct": p, "measurable": True}
            for d, ps in preds_by_day.items() for i, p in enumerate(ps)]
    df = pd.DataFrame(rows)
    if measurable is not None:
        df["measurable"] = measurable
    return df


def test_fires_per_day_counts_quiet_days_as_zero():
    # ADR 0004: 2 өдөр. 1-д 3 🔥 (≥ 25%), 2-т 0 🔥 (нам гүм өдөр) -> дунджаар 1.5
    df = fire_frame({"2025-08-01": [0.30, 0.25, 0.90, 0.10], "2025-08-02": [0.24, -0.5]})
    assert scoring.fires_per_day(df, 0.25) == 1.5


def test_fires_per_day_ignores_unmeasurable_topics():
    df = fire_frame({"2025-08-01": [0.50, 0.60]}, measurable=[True, False])
    assert scoring.fires_per_day(df, 0.25) == 1.0


def test_tuned_threshold_gives_target_fires_per_day():
    # 2 өдөр, зорилго өдөрт 1.5 🔥 -> нийт 3 🔥: хэмжигдэх сэдвийн 3 дахь хамгийн өндөр таамаг = 0.60.
    # Хэмжигдэхгүй 5.0 нь тооцогдохгүй.
    df = fire_frame({"2025-08-01": [0.90, 0.60, 0.20, 5.0], "2025-08-02": [0.70, 0.40, 0.30, 0.10]},
                    measurable=[True, True, True, False, True, True, True, True])
    T = scoring.tune_threshold(df, target=1.5)
    assert T == pytest.approx(0.60)
    assert scoring.fires_per_day(df, T) == 1.5


def test_tuned_threshold_never_below_25pct():
    # ADR 0004: зорилгод хүрэхийн тулд 10% хүртэл буулгах шаардлагатай ч T = 25% хэвээр (өдөрт 0.5 🔥)
    df = fire_frame({"2025-08-01": [0.40, 0.10], "2025-08-02": [0.20, 0.05]})
    assert scoring.tune_threshold(df, target=1.0) == 0.25


def test_default_target_is_inside_5_to_10_per_day():
    assert 5 <= scoring.FIRES_PER_DAY_TARGET <= 10


def test_residual_quantiles_are_10_and_90_of_actual_minus_predicted():
    # residual = Δ − Δ̂ = −0.5, −0.4, …, +0.5 (11 утга) -> 10%: −0.4, 90%: +0.4
    resid = np.round(np.arange(-5, 6) / 10, 1)
    delta_hat = np.full(11, 0.3)
    lo, hi = scoring.residual_quantiles(delta_hat + resid, delta_hat)
    assert (lo, hi) == pytest.approx((-0.4, 0.4))


def test_interval_pct_shifts_prediction_by_quantiles_in_log_scale():
    # x_0 = 0.5, Δ̂ = 0.11, квантил ±0.11 -> Δ [0, 0.22] -> [0%, +74%] (ADR 0003)
    lo, hi = scoring.interval_pct(np.log1p(0.5), 0.11, -0.11, 0.11)
    assert (lo, hi) == pytest.approx((0.0, 0.74), abs=0.005)


def test_tuned_threshold_before_floor_is_reported():
    # T нь 25% хэвээр ч max()-ийн нөгөө тал (өдөрт 1 🔥 гаргах босго = 0.20) харагдах ёстой
    df = fire_frame({"2025-08-01": [0.40, 0.10], "2025-08-02": [0.20, 0.05]})
    assert scoring.tuned_threshold(df, target=1.0) == pytest.approx(0.20)
