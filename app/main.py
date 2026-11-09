"""
Шуугиан — вэб сервер (FastAPI).

Ажиллуулах:  uvicorn app.main:app --reload
Дараа нь браузерт:  http://127.0.0.1:8000

ОДООГООР: app/mock/ доторх жишээ өгөгдлийг өгнө.
Мягмар–Лхагва: сургасан LightGBM model-ийг ачаалж, бодит таамаг өгнө.
"""
import json
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

HERE = Path(__file__).resolve().parent
MOCK = HERE / "mock"

app = FastAPI(title="Шуугиан API")


@lru_cache(maxsize=8)
def _load(name: str) -> dict:
    return json.loads((MOCK / f"{name}.json").read_text(encoding="utf-8"))


@app.get("/api/trending")
def trending():
    """Өчигдрийн хамгийн их шуугисан сэдвүүд + ирэх 3 өдрийн таамаг."""
    return _load("trending")


@app.get("/api/categories")
def categories():
    """10 ангилал тус бүрийн тэргүүлэх сэдвүүд."""
    return _load("categories")


@app.get("/api/topic/{article}")
def topic(article: str):
    """Нэг сэдвийн 180 өдрийн түүх + таамаг."""
    t = _load("topics")["topics"].get(article)
    if t is None:
        raise HTTPException(404, "Ийм сэдэв манай жагсаалтад алга")
    return {"asof": _load("topics")["asof"], "mock": True, **t}


@app.get("/api/map")
def attention_map():
    """Анхаарлын газрын зураг: өчигдрийн топ 40 сэдэв (уншилт ба өсөлт)."""
    return _load("map")


@app.get("/api/insights")
def insights():
    """"Сонирхолтой" хуудасны баримтууд (бодит өгөгдлөөс тооцоолсон)."""
    return _load("insights")


@app.get("/api/model")
def model():
    """Model-ийн үнэлгээ: baseline-тай харьцуулалт, сургалтын муруй, feature importance."""
    return _load("model")


# Вэб хуудас: index.html ба түүний файлууд (assets/, fonts/, app.js ...) язгуур замаас.
# API замууд дээр бүртгэгдсэн тул түрүүлж таарна; бусад бүх зам static файл руу.
app.mount("/", StaticFiles(directory=HERE / "static", html=True), name="site")
