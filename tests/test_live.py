"""src/live.py: серверийн өгөгдлийн cache-ийг өдөр бүр шинэчлэх (ADR 0008).  Ажиллуулах:  pytest -q"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import live  # noqa: E402

TODAY = pd.Timestamp("2026-11-11")          # D
TOTAL = 200_000_000


def cache_ending(end: pd.Timestamp, days: int = 40) -> live.RawCache:
    """2 сэдэв (нэг нь alias-тай) + total_views, `end` өдрөөр дуусна."""
    dates = pd.date_range(end - pd.Timedelta(days=days - 1), end)
    pv = pd.DataFrame([{"date": d, "article": a, "category": c, "views": 1000}
                       for a, c in (("A", "politics"), ("B", "viral")) for d in dates])
    alias = pd.DataFrame({"date": dates, "views": 10, "old_title": "A_old", "article": "A"})
    total = pd.DataFrame({"date": dates, "total_views": TOTAL})
    return live.RawCache(pv, alias, total)


class FakeFetcher:
    """Wikimedia-гийн оронд: `published_through` хүртэлх өдрүүдийг буцаана, хүсэлт бүрийг тэмдэглэнэ."""

    def __init__(self, published_through=TODAY - pd.Timedelta(days=1), fail=False, total_scale=1.0):
        self.published_through, self.fail, self.total_scale = published_through, fail, total_scale
        self.calls = []

    def _days(self, start, end):
        return pd.date_range(start, min(end, self.published_through))

    def total(self, start, end):
        self.calls.append(("total", None, start, end))
        if self.fail:
            raise ConnectionError("Wikimedia унасан")
        d = self._days(start, end)
        return pd.DataFrame({"date": d, "total_views": int(TOTAL * self.total_scale)})

    def article(self, title, start, end):
        self.calls.append(("article", title, start, end))
        if self.fail:
            raise ConnectionError("Wikimedia унасан")
        d = self._days(start, end)
        return pd.DataFrame({"date": d, "views": 2000})


def test_only_missing_recent_days_are_requested():
    """Cache D−4-өөр дууссан бол зөвхөн D−3 … D−1 (өчигдөр) татагдана, сэдэв бүр + alias + total."""
    f = FakeFetcher()
    res = live.update_cache(cache_ending(TODAY - pd.Timedelta(days=4)), f, TODAY)
    want = (pd.Timestamp("2026-11-08"), pd.Timestamp("2026-11-10"))
    assert {(s, e) for _, _, s, e in f.calls} == {want}
    assert sorted(t for k, t, _, _ in f.calls if k == "article") == ["A", "A_old", "B"]
    assert res.status == live.OK
    assert res.cache.end == pd.Timestamp("2026-11-10")
    new = res.cache.pageviews
    assert len(new[(new["article"] == "B") & (new["date"] > "2026-11-07")]) == 3
    assert set(new.loc[new["article"] == "B", "category"]) == {"viral"}


def test_cache_is_kept_when_fetcher_fails():
    """API унавал: хуучин cache яг хэвээр, статус ERROR, ~3 цагийн дараа дахин оролдоно."""
    old = cache_ending(TODAY - pd.Timedelta(days=3))
    res = live.update_cache(old, FakeFetcher(fail=True), TODAY)
    assert res.cache is old
    assert res.status == live.ERROR and res.needs_retry
    assert "унасан" in res.message


def test_unpublished_yesterday_keeps_complete_days_and_asks_for_retry():
    """Өчигдөр (D−1) хараахан гараагүй: D−3, D−2-ыг нэмнэ, статус PARTIAL -> дахин оролдоно."""
    f = FakeFetcher(published_through=TODAY - pd.Timedelta(days=2))
    res = live.update_cache(cache_ending(TODAY - pd.Timedelta(days=4)), f, TODAY)
    assert res.cache.end == pd.Timestamp("2026-11-09")
    assert res.cache.pageviews["date"].max() == pd.Timestamp("2026-11-09")
    assert res.status == live.PARTIAL and res.needs_retry


def test_nothing_published_keeps_cache_and_asks_for_retry():
    """Шинэ өдөр нэг ч гараагүй: нийтлэл татахгүй, cache хэвээр, NOT_PUBLISHED."""
    old = cache_ending(TODAY - pd.Timedelta(days=2))
    f = FakeFetcher(published_through=TODAY - pd.Timedelta(days=2))
    res = live.update_cache(old, f, TODAY)
    assert res.cache is old and res.status == live.NOT_PUBLISHED and res.needs_retry
    assert [k for k, *_ in f.calls] == ["total"]


def test_incomplete_total_views_is_not_accepted():
    """total_views хэт бага (жишээ нь ердийнхийн 10%, нэгтгэл дуусаагүй) бол тэр өдрийг авахгүй."""
    old = cache_ending(TODAY - pd.Timedelta(days=2))
    res = live.update_cache(old, FakeFetcher(total_scale=0.1), TODAY)
    assert res.cache is old and res.status == live.NOT_PUBLISHED


def test_up_to_date_cache_requests_nothing():
    f = FakeFetcher()
    res = live.update_cache(cache_ending(TODAY - pd.Timedelta(days=1)), f, TODAY)
    assert res.status == live.UP_TO_DATE and not res.needs_retry and f.calls == []


@pytest.mark.parametrize("status,retried,want", [
    (live.NOT_PUBLISHED, False, "2026-11-11 09:00"),   # анхны бүтэлгүйтэл -> 3 цагийн дараа нэг удаа
    (live.ERROR, True, "2026-11-12 03:00"),            # дахин оролдлого ч бүтэлгүй -> маргаашийн ээлж хүртэл cache-ээр
    (live.OK, False, "2026-11-12 03:00"),
    (live.UP_TO_DATE, False, "2026-11-12 03:00"),
])
def test_retry_once_three_hours_later_then_wait_for_next_day(status, retried, want):
    now = pd.Timestamp("2026-11-11 06:00")
    when, is_retry = live.next_attempt(status, now, retried)
    assert when == pd.Timestamp(want)
    assert is_retry == (status in (live.NOT_PUBLISHED, live.ERROR) and not retried)


def test_day_without_article_data_is_not_accepted_even_if_total_is_published():
    """total_views D өдөрт гарсан ч сэдвүүдийн өгөгдөл хоцорвол: тэр өдрийг 0 уншилт гэж авахгүй (PARTIAL)."""

    class LaggingArticles(FakeFetcher):
        def article(self, title, start, end):
            df = super().article(title, start, end)
            return df[df["date"] < TODAY - pd.Timedelta(days=1)]     # өчигдрийн нийтлэлийн өгөгдөл хараахан алга

    res = live.update_cache(cache_ending(TODAY - pd.Timedelta(days=3)), LaggingArticles(), TODAY)
    assert res.cache.end == pd.Timestamp("2026-11-09")
    assert res.cache.pageviews["date"].max() == pd.Timestamp("2026-11-09")
    assert res.status == live.PARTIAL and res.needs_retry
