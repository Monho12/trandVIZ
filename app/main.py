"""
Шуугиан — вэб сервер (FastAPI). Model сайтын ард ажиллана (ADR 0008).

Ажиллуулах:  uvicorn app.main:app --reload
Дараа нь браузерт:  http://127.0.0.1:8000

- Эхлэхдээ `app/model/`-оос ялагч алгоритмын 3 model + `meta.json`-ийг ачаална.
- Өгөгдөл: `data/processed/` (image дотор ирдэг) эсвэл түүнээс шинэ `data/live/` cache.
  Арын thread өдөрт нэг удаа зөвхөн дутуу сүүлийн өдрүүдийг Wikimedia-аас татна (src/live.py).
  D гараагүй / алдаа бол ~3 цагийн дараа нэг удаа дахин оролдоно, тэгээд ч болохгүй бол сүүлийн cache.
- /api/topic, /api/categories, /api/trending, /api/map: хүсэлт бүрт model -> scoring (src/serve.py).
- /api/model: ачаалагдсан алгоритм, сургасан огноо, өгөгдлийн asof + Загвар хуудасны үнэлгээ.

Орчны хувьсагч:
  SHUUGIAN_REFRESH=0       Wikimedia-аас татахгүй (offline, тест)
  SHUUGIAN_DATA_DIR=...    шинэчилсэн cache-ийг хадгалах хавтас (анхдагч: data/live)
"""
from __future__ import annotations

import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src import evaluate, live, serve, train

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
PROCESSED = ROOT / "data" / "processed"
LIVE_DIR = Path(os.environ.get("SHUUGIAN_DATA_DIR", ROOT / "data" / "live"))
HTTP_CACHE = LIVE_DIR / "http"

log = logging.getLogger("shuugian")


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None)


def load_raw() -> live.RawCache:
    """data/live/ нь data/processed/-оос шинэ бол түүнийг, үгүй бол image-ийн түүхийг."""
    base = live.RawCache.load(PROCESSED)
    try:
        newer = live.RawCache.load(LIVE_DIR)
        if newer.end > base.end:
            return newer
    except (FileNotFoundError, OSError, ValueError):
        pass
    return base


class Server:
    """Ачаалсан model + өгөгдлийн snapshot + өдөр тутмын шинэчлэлт. snapshot-ийг бүхэлд нь сольдог."""

    def __init__(self):
        self.model = None
        self.raw: live.RawCache | None = None
        self.snapshot: serve.Snapshot | None = None
        self.loaded_at = None
        self.refresh = {"enabled": False, "status": None, "message": "", "at": None, "next": None}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, refresh: bool = True) -> None:
        self.model = train.load()
        self.raw = load_raw()
        self.snapshot = serve.Snapshot.from_raw(self.raw)
        self.loaded_at = utc_now()
        self.refresh["enabled"] = refresh
        if refresh:
            self._thread = threading.Thread(target=self._loop, name="wiki-refresh", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        fetcher, retried = live.WikiFetcher(HTTP_CACHE), False
        while not self._stop.is_set():
            now = utc_now()
            res = live.update_cache(self.raw, fetcher, now)
            if res.cache is not self.raw:
                try:
                    snap = serve.Snapshot.from_raw(res.cache)
                    res.cache.save(LIVE_DIR)
                    self.raw, self.snapshot = res.cache, snap
                except Exception as e:   # шинэ өгөгдлийг боловсруулж чадсангүй: хуучин snapshot-оор үргэлжлүүлнэ
                    res = live.UpdateResult(self.raw, live.ERROR, f"боловсруулах: {type(e).__name__}: {e}")
            when, retried = live.next_attempt(res.status, now, retried)
            self.refresh.update(status=res.status, message=res.message, at=now.isoformat(timespec="seconds"),
                                next=when.isoformat(timespec="seconds"))
            log.warning("Wikimedia шинэчлэлт: %s %s (asof %s), дараагийнх %s",
                        res.status, res.message, self.raw.end.date(), when)
            self._stop.wait(max((when - utc_now()).total_seconds(), 1))


state = Server()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    state.start(refresh=os.environ.get("SHUUGIAN_REFRESH", "1") != "0")
    yield
    state.stop()


app = FastAPI(title="Шуугиан API", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get("/api/trending")
def trending():
    """Top-10 (хэмжигдэх сэдэв, таамагласан pct(h3)-ээр) эхэнд, дараа нь бусад бүх сэдэв."""
    return serve.trending(state.model, state.snapshot, utc_now())


@app.get("/api/categories")
def categories():
    """Ангилал тус бүрийн хамгийн их уншигдсан сэдвүүд (вирал -> "Бусад")."""
    return serve.categories(state.model, state.snapshot, utc_now())


@app.get("/api/topic/{article}")
def topic(article: str):
    """Нэг сэдвийн 180 өдрийн түүх + ирэх 3 өдрийн таамаг."""
    t = serve.topic(state.model, state.snapshot, article, utc_now())
    if t is None:
        raise HTTPException(404, "Ийм сэдэв манай жагсаалтад алга")
    return t


@app.get("/api/map")
def attention_map():
    """Анхаарлын газрын зураг: asof өдрийн хамгийн их уншигдсан 40 сэдэв."""
    return serve.attention_map(state.model, state.snapshot, utc_now())


@lru_cache(maxsize=1)
def _insights() -> dict:
    return json.loads((DATA / "insights.json").read_text(encoding="utf-8"))


@app.get("/api/insights")
def insights():
    """"Сонирхолтой" хуудасны баримтууд (бодит өгөгдлөөс, app/data/make_insights.py)."""
    return _insights()


@app.get("/api/model")
def model():
    """Сайтын ард ажиллаж буй model: алгоритм, сургасан огноо, өгөгдлийн asof (ADR 0008)
    + Загвар хуудасны test-ийн үнэлгээ (meta.json-оос)."""
    meta, snap = state.model.meta, state.snapshot
    page = evaluate.model_page(meta)
    return {
        **page,
        **serve.meta_block(snap.asof, utc_now()),
        "test_end": page["asof"],
        "live": {
            "algo": meta["algo"], "algo_name": evaluate.ALGO_NAME[meta["algo"]],
            "trained_at": meta["trained_at"], "data_asof": snap.asof.strftime("%Y-%m-%d"),
            "loaded_at": state.loaded_at.isoformat(timespec="seconds"),
            "snapshot_built_at": snap.built_at.isoformat(timespec="seconds"),
            "horizons": meta["horizons"], "n_features": len(meta["features"]),
            "fire_T": meta["fire"]["T"], "topics": int(snap.clean["article"].nunique()),
            "refresh": dict(state.refresh),
        },
    }


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")
