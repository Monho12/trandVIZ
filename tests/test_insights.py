""""Сонирхолтой" хуудасны баримт (app/data/make_insights.py -> app/data/insights.json, issue #33).
Сонголтын дүрмийг жижиг хүснэгтээр, файлыг бодит агуулгаар нь шалгана.  pytest -q"""
import json
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["SHUUGIAN_REFRESH"] = "0"
from app.data import make_insights as mi  # noqa: E402

DOW = range(7)   # 0 = Даваа ... 6 = Ням


def weekday_table(rows: dict) -> pd.DataFrame:
    """Ангилал x гараг, 100 = долоо хоногийн дундаж."""
    return pd.DataFrame.from_dict(rows, orient="index", columns=DOW)


def test_weekday_pick_takes_the_two_categories_with_the_widest_swing():
    idx = weekday_table({
        "flat": [100, 101, 99, 100, 100, 100, 100],        # хэлбэлзэл 2
        "wide": [100, 100, 100, 100, 80, 100, 140],        # 60
        "mid": [100, 100, 100, 120, 100, 90, 90],          # 30
        "small": [105, 100, 100, 100, 100, 100, 95],       # 10
    })
    assert mi.weekday_pick(idx) == [{"key": "wide", "peak": 6, "low": 4}, {"key": "mid", "peak": 3, "low": 5}]


def test_weekday_pick_breaks_a_tied_peak_toward_the_start_of_the_week():
    idx = weekday_table({"a": [90, 110, 100, 110, 90, 100, 100], "b": [100, 100, 100, 100, 100, 100, 100]})
    assert mi.weekday_pick(idx)[0] == {"key": "a", "peak": 1, "low": 0}   # Мя = Пү -> Мя; Да = Ба -> Да


def monthly(first: str, last: str, peaks: dict) -> pd.DataFrame:
    """Сар бүр 10 уншилттай хүснэгт; peaks: {нийтлэл: {"YYYY-MM": утга}}."""
    months = pd.date_range(first, last, freq="MS")
    df = pd.DataFrame(10.0, index=months, columns=list(peaks))
    for name, cells in peaks.items():
        for month, v in cells.items():
            df.loc[pd.Timestamp(month + "-01"), name] = v
    return df


def test_holiday_peak_comes_from_the_last_complete_year_only():
    # 2026 он 3 сартай: 2026-01 бүх цувааны хамгийн өндөр ч оргил болохгүй
    hol = monthly("2024-01", "2026-03", {"H": {"2024-10": 50, "2025-10": 40, "2026-01": 999}})
    got = mi.holiday_peaks(hol)
    assert got == {"full_years": [2024, 2025], "incomplete_year": 2026, "peaks": {"H": "2025-10"}}


def test_no_incomplete_year_when_the_data_ends_in_december():
    got = mi.holiday_peaks(monthly("2024-01", "2025-12", {"H": {"2025-02": 50}}))
    assert got["full_years"] == [2024, 2025] and got["incomplete_year"] is None


def test_ranges_are_inclusive_windows_ending_on_asof():
    got = mi.ranges(pd.Timestamp("2021-01-01"), pd.Timestamp("2026-11-06"))
    assert got["categories"] == {"from": "2026-10-08", "to": "2026-11-06"}     # 30 хоног, хоёр үзүүрээ оруулаад
    assert got["mongolia"] == {"from": "2025-11-07", "to": "2026-11-06"}       # 365 хоног
    assert got["decay"] == {"from": "2021-01-01", "to": "2026-11-06"}          # бүх өгөгдөл
    assert got["holidays"]["from"] == "2023-01-01"


def test_window_keeps_exactly_the_days_the_range_names():
    days = pd.DataFrame({"date": pd.date_range("2026-09-01", "2026-11-06")})
    kept = mi.window(days, pd.Timestamp("2026-11-06"), "categories")["date"]
    assert (kept.min().strftime("%Y-%m-%d"), kept.max().strftime("%Y-%m-%d"), len(kept)) == ("2026-10-08", "2026-11-06", 30)


# ── Бодит файл (сайт үүнийг /api/insights-ээр уншина) ──
CARDS = {"decay", "categories", "weekday", "holidays", "mongolia"}


@pytest.fixture(scope="module")
def real() -> dict:
    return json.loads((ROOT / "app" / "data" / "insights.json").read_text(encoding="utf-8"))


def test_every_card_has_a_date_range_ending_on_asof(real):
    assert set(real["ranges"]) == CARDS
    for r in real["ranges"].values():
        assert r["from"] < r["to"] == real["asof"]


def test_real_weekday_picks_are_the_top_two_swings_and_name_each_peak_day(real):
    wd = real["weekday"]
    swing = {k: max(v) - min(v) for k, v in wd.items()}
    picks = real["weekday_pick"]
    assert [p["key"] for p in picks] == sorted(swing, key=swing.get, reverse=True)[:2]
    for p in picks:
        v = wd[p["key"]]
        assert v[p["peak"]] == max(v) and v[p["low"]] == min(v)


def test_real_holidays_peak_in_the_same_month_every_complete_year(real):
    h = real["holidays"]
    assert len(h["full_years"]) >= 2 and h["incomplete_year"] not in h["full_years"]
    for name, values in h["series"].items():
        by_month = dict(zip(h["months"], values))
        for year in h["full_years"]:
            assert all(f"{year}-{m:02d}" in by_month for m in range(1, 13))     # бүтэн жил = 12 сар нь бүгд
            top = max((f"{year}-{m:02d}" for m in range(1, 13)), key=by_month.get)
            assert top[5:] == h["peaks"][name][5:], (name, year)
        assert h["peaks"][name][:4] == str(h["full_years"][-1])
    assert {n: p[5:] for n, p in h["peaks"].items()} == {"Halloween": "10", "Christmas": "12", "Valentine's Day": "02"}


def test_real_counts_come_from_the_data(real):
    assert (real["topics_n"], real["curated_n"], real["mongolia_n"]) == (301, 151, 15)   # сэдвийн жагсаалт тогтмол
    assert 0 < real["decay_n"] <= real["topics_n"] - real["curated_n"]


def test_api_serves_the_file_as_is(real):
    testclient = pytest.importorskip("fastapi.testclient")
    from app.main import app
    with testclient.TestClient(app) as c:
        assert c.get("/api/insights").json() == real
