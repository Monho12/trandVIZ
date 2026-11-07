"""
Wikipedia-ийн хандалтын (pageviews) API-тай ярилцах жижиг клиент.

Гол санаа:
- Wikimedia API нь цагт хязгаартай тооны хүсэлт зөвшөөрдөг (rate limit).
  Тиймээс хүсэлт бүрийн хооронд бага зэрэг хүлээж, 429 ("хэт олон хүсэлт")
  алдаа ирвэл заасан хугацаагаар хүлээгээд дахин оролдоно.
- Татсан хариу бүрийг дискэнд (cache) хадгална. Дахин ажиллуулахад
  интернэтээс биш дискнээс уншина -> хурдан, API-г дэмий ачаалахгүй.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

# Wikimedia-ийн дүрмээр хэн хүсэлт илгээж байгааг User-Agent-д тодорхой бичих ёстой
USER_AGENT = "Shuugiaan/0.1 (https://github.com/Monho12/trandVIZ; student data-mining project)"
BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
PROJECT = "en.wikipedia"

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})
_last_call = 0.0


def _get_json(url: str, cache_dir: Path | None, min_interval: float = 2.0, max_retries: int = 25):
    """URL-аас JSON татна. Cache байвал түүнийг уншина. 404 бол None буцаана."""
    global _last_call
    cache_file = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".json")
        if cache_file.exists():
            return json.loads(cache_file.read_text())

    for attempt in range(max_retries):
        # Хүсэлт хоорондын хамгийн бага зай (API-г хүндэтгэх)
        wait = min_interval - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()

        r = _session.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            if cache_file is not None:
                cache_file.write_text(json.dumps(data))
            return data
        if r.status_code == 404:
            # Нийтлэл байхгүй эсвэл тухайн хугацаанд өгөгдөлгүй
            if cache_file is not None:
                cache_file.write_text("null")
            return None
        if r.status_code in (429, 500, 502, 503, 504):
            # Retry-After байвал түүнийг дагана, үгүй бол exponential back-off
            retry_after = r.headers.get("Retry-After")
            sleep_s = float(retry_after) if retry_after and retry_after.isdigit() else min(5 * 2**attempt, 120)
            time.sleep(sleep_s)
            continue
        r.raise_for_status()
    raise RuntimeError(f"Олон удаа оролдоод бүтсэнгүй: {url}")


def _fmt(d) -> str:
    return pd.Timestamp(d).strftime("%Y%m%d")


def article_daily(title: str, start, end, cache_dir: Path | None = None) -> pd.DataFrame:
    """Нэг нийтлэлийн өдөр тутмын ХҮНИЙ хандалт (agent=user -> ботыг хассан)."""
    t = quote(title.replace(" ", "_"), safe="")
    url = f"{BASE}/per-article/{PROJECT}/all-access/user/{t}/daily/{_fmt(start)}/{_fmt(end)}"
    data = _get_json(url, cache_dir)
    if not data or not data.get("items"):
        return pd.DataFrame(columns=["date", "views"])
    df = pd.DataFrame(data["items"])
    df["date"] = pd.to_datetime(df["timestamp"].str[:8], format="%Y%m%d")
    return df[["date", "views"]]


def total_daily(start, end, cache_dir: Path | None = None) -> pd.DataFrame:
    """Англи Wikipedia-ийн НИЙТ өдөр тутмын хүний хандалт (анхаарлын хувийг тооцоход хэрэгтэй)."""
    url = f"{BASE}/aggregate/{PROJECT}/all-access/user/daily/{_fmt(start)}/{_fmt(end)}"
    data = _get_json(url, cache_dir)
    df = pd.DataFrame(data["items"])
    df["date"] = pd.to_datetime(df["timestamp"].str[:8], format="%Y%m%d")
    return df[["date", "views"]].rename(columns={"views": "total_views"})


def top_articles(year: int, month: int, day: int | None = None, cache_dir: Path | None = None) -> pd.DataFrame:
    """Тухайн өдөр (эсвэл сар) хамгийн их уншигдсан 1000 нийтлэл."""
    d = f"{day:02d}" if day else "all-days"
    url = f"{BASE}/top/{PROJECT}/all-access/{year}/{month:02d}/{d}"
    data = _get_json(url, cache_dir)
    if not data:
        return pd.DataFrame(columns=["article", "views", "rank"])
    return pd.DataFrame(data["items"][0]["articles"])[["article", "views", "rank"]]


# Нийтлэл биш хуудсууд болон тохиромжгүй контентыг шүүх
_NON_ARTICLE_PREFIXES = (
    "Special:", "Wikipedia:", "Portal:", "File:", "Help:", "Talk:", "User:",
    "Template:", "Category:", "Draft:", "Module:", "MediaWiki:",
)
_BLOCK_WORDS = ("porn", "xxx", "sex", "hentai", "nude", "onlyfans", "xvideos", "xhamster", "erotic")


def is_real_article(title: str) -> bool:
    t = str(title)
    low = t.lower()
    if t in ("Main_Page", "-") or t.startswith(_NON_ARTICLE_PREFIXES):
        return False
    if any(w in low for w in _BLOCK_WORDS):
        return False
    # Жил бүр шинээр үүсдэг ("Deaths in 2025" г.м.) нийтлэлүүд жил солигдоход тэглэгддэг
    if low.startswith(("deaths_in_", "list_of_")):
        return False
    return True
