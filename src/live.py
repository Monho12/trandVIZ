"""
Серверийн өгөгдлийн cache (ADR 0008): model сайтын ард ажиллахад хэрэгтэй түүхий өгөгдөл.

- Эхлэл нь `data/processed/`-ийн боловсруулсан түүх (Docker image дотор хамт ирнэ).
- Өдөрт нэг удаа зөвхөн **дутуу сүүлийн өдрүүдийг** (сүүлийн огноо + 1 … өчигдөр) татна. 400 хоног дахин татахгүй.
- D өдөр гараагүй эсвэл `total_views` дутуу бол OK биш статус буцаана -> сервер ~3 цагийн дараа нэг удаа дахин оролдоно.
  Татах үед алдаа гарвал (API унасан) хуучин cache хэвээр үлдэнэ.

Татагч (fetcher) нь гаднаас өгөгдөнө: сервер `WikiFetcher`-ийг, тест хуурамч татагчийг ашиглана.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd

OK, PARTIAL, NOT_PUBLISHED, ERROR, UP_TO_DATE = "ok", "partial", "not_published", "error", "up_to_date"
TOTAL_MIN_SHARE = 0.5   # D өдрийн total_views сүүлийн 28 өдрийн медианы 50%-иас бага бол "дутуу" гэж үзнэ
FILES = {"pageviews": "pageviews.parquet", "alias": "alias_pageviews.parquet", "total": "total_views.parquet"}


class Fetcher(Protocol):
    def total(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """[date, total_views]: англи Wikipedia-ийн нийт хүний уншилт, гарсан өдрүүд л."""

    def article(self, title: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """[date, views]: нэг нийтлэлийн хүний уншилт. 0 уншилттай өдрийг API буцаадаггүй."""


@dataclass(frozen=True)
class RawCache:
    """`data/processed/`-ийн 3 parquet-тэй ижил бүтэцтэй түүхий өгөгдөл."""
    pageviews: pd.DataFrame      # [date, article, category, views]
    alias: pd.DataFrame          # [date, views, old_title, article]
    total: pd.DataFrame          # [date, total_views]

    @property
    def end(self) -> pd.Timestamp:
        """Cache-ийн сүүлийн бүрэн өдөр (total_views байгаа сүүлийн өдөр)."""
        return pd.Timestamp(self.total["date"].max())

    @classmethod
    def load(cls, directory: Path) -> "RawCache":
        d = Path(directory)
        return cls(*(pd.read_parquet(d / FILES[k]) for k in ("pageviews", "alias", "total")))

    def save(self, directory: Path) -> None:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        for k, df in (("pageviews", self.pageviews), ("alias", self.alias), ("total", self.total)):
            tmp = d / (FILES[k] + ".tmp")
            df.to_parquet(tmp, index=False)
            tmp.replace(d / FILES[k])


@dataclass(frozen=True)
class UpdateResult:
    cache: RawCache
    status: str                  # OK / PARTIAL / NOT_PUBLISHED / ERROR / UP_TO_DATE
    message: str = ""

    @property
    def needs_retry(self) -> bool:
        """D өдөр бүрэн ирээгүй эсвэл алдаа гарсан: ~3 цагийн дараа нэг удаа дахин оролдоно (ADR 0008)."""
        return self.status in (PARTIAL, NOT_PUBLISHED, ERROR)


RETRY_AFTER = pd.Timedelta(hours=3)   # D гараагүй / алдаа -> нэг удаа дахин оролдох хугацаа (ADR 0008)
DAILY_HOUR_UTC = 3                    # өдрийн ээлж: 03:00 UTC (УБ 11:00). Wikimedia D өдрийг D+1-ний эхээр гаргадаг


def next_attempt(status: str, now: pd.Timestamp, retried: bool) -> tuple[pd.Timestamp, bool]:
    """Дараагийн татах оролдлого хэзээ вэ, тэр нь дахин оролдлого мөн үү.
    D гараагүй / дутуу / алдаа бөгөөд хараахан дахин оролдоогүй бол RETRY_AFTER-ийн дараа НЭГ удаа.
    Бусад үед (амжилттай, эсвэл дахин оролдлого ч бүтэлгүй) маргаашийн DAILY_HOUR_UTC хүртэл сүүлийн cache-ээр."""
    now = pd.Timestamp(now)
    if status in (PARTIAL, NOT_PUBLISHED, ERROR) and not retried:
        return now + RETRY_AFTER, True
    daily = now.normalize() + pd.Timedelta(hours=DAILY_HOUR_UTC)
    return (daily if daily > now else daily + pd.Timedelta(days=1)), False


def missing_days(cache_end: pd.Timestamp, today: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """Татах ёстой хугацаа: cache_end + 1 … өчигдөр (today − 1). Дутуу өдөргүй бол None."""
    start = pd.Timestamp(cache_end).normalize() + pd.Timedelta(days=1)
    end = pd.Timestamp(today).normalize() - pd.Timedelta(days=1)
    return (start, end) if start <= end else None


def update_cache(cache: RawCache, fetcher: Fetcher, today: pd.Timestamp) -> UpdateResult:
    """Cache-д дутуу байгаа сүүлийн өдрүүдийг fetcher-ээр татаж нэмнэ. Оролтын cache-ийг өөрчлөхгүй."""
    span = missing_days(cache.end, today)
    if span is None:
        return UpdateResult(cache, UP_TO_DATE)
    start, end = span
    try:
        return _fetch(cache, fetcher, start, end)
    except Exception as e:   # API унасан, сүлжээ, 5xx: хуучин cache-ээр үргэлжлүүлнэ
        return UpdateResult(cache, ERROR, f"{type(e).__name__}: {e}")


def _fetch(cache: RawCache, fetcher: Fetcher, start: pd.Timestamp, end: pd.Timestamp) -> UpdateResult:
    tot = complete_days(fetcher.total(start, end), cache.total, start, end)
    if tot.empty:
        return UpdateResult(cache, NOT_PUBLISHED, f"{start.date()} өдрийн total_views хараахан гараагүй/дутуу")
    got_end = tot["date"].max()

    arts = cache.pageviews.drop_duplicates("article")[["article", "category"]]
    pv = [cache.pageviews]
    for a, c in arts.itertuples(index=False):
        df = fetcher.article(a, start, got_end)
        pv.append(df.assign(article=a, category=c)[["date", "article", "category", "views"]])
    al = [cache.alias]
    for old, new in cache.alias.drop_duplicates("old_title")[["old_title", "article"]].itertuples(index=False):
        df = fetcher.article(old, start, got_end)
        al.append(df.assign(old_title=old, article=new)[["date", "views", "old_title", "article"]])

    new_cache = RawCache(_cat(pv), _cat(al), _cat([cache.total, tot[["date", "total_views"]]]))
    if got_end < end:
        return UpdateResult(new_cache, PARTIAL, f"{got_end.date()} хүртэл нэмлээ, {end.date()} хараахан гараагүй/дутуу")
    return UpdateResult(new_cache, OK, f"{start.date()} … {end.date()} нэмлээ")


def complete_days(new_total: pd.DataFrame, old_total: pd.DataFrame, start, end) -> pd.DataFrame:
    """start-аас эхэлсэн, тасралтгүй, бүрэн өдрүүдийн total_views. Бүрэн = сүүлийн 28 өдрийн медианы
    TOTAL_MIN_SHARE-ээс их (нэгтгэл дуусаагүй өдрийн нийт уншилт хэт бага гардаг). Эхний дутуу өдрөөс зогсоно."""
    ref = float(old_total.sort_values("date")["total_views"].tail(28).median())
    t = new_total[(new_total["date"] >= start) & (new_total["date"] <= end)].set_index("date")["total_views"]
    keep = []
    for d in pd.date_range(start, end):
        if d not in t.index or not t[d] > TOTAL_MIN_SHARE * ref:
            break
        keep.append(d)
    return pd.DataFrame({"date": keep, "total_views": [int(t[d]) for d in keep]})


def _cat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    out = pd.concat([f for f in frames if len(f)], ignore_index=True)
    if "views" in out:
        out["views"] = out["views"].astype("int64")
    return out


class WikiFetcher:
    """Wikimedia Pageviews API-аар татагч (src/wiki.py: User-Agent, throttle, 429 back-off).

    total_views-ийг cache-гүй татна: D өдөр хараахан гараагүй хариуг дискэнд хадгалбал дахин оролдлого мөн
    тэр хуучин хариуг уншина. Нийтлэлийг зөвхөн бүрэн гэж шалгасан өдрүүдээр татдаг тул дискний cache хэвээр."""

    def __init__(self, cache_dir: Path | None, min_interval: float = 0.5, max_retries: int = 4):
        self.cache_dir, self.kw = cache_dir, {"min_interval": min_interval, "max_retries": max_retries}

    def total(self, start, end) -> pd.DataFrame:
        from src import wiki
        return wiki.total_daily(start, end, cache_dir=None, **self.kw)

    def article(self, title, start, end) -> pd.DataFrame:
        from src import wiki
        return wiki.article_daily(title, start, end, cache_dir=self.cache_dir, **self.kw)
