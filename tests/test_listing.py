"""app/static/listing.js: "Бүх сэдэв" хуудсыг ангиллаар бүлэглэх (ADR 0013).
Цэвэр функцийг node-оор дуудна (browser-гүй).  pytest -q"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SHUUGIAN_REFRESH"] = "0"

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
NODE = shutil.which("node")
ORDER = ["politics", "sports"]   # нүүрний дараалал (app.js-ийн ORDER-ийн жишээ)
OTHER = "Бусад"


def listing(fn: str, *args):
    """Listing.<fn>(*args)-ийн утга (fn нь тогтмол бол түүний утга). Аргументыг stdin-ээр дамжуулна (301 сэдэв багтана)."""
    if NODE is None:
        pytest.skip("node алга")
    code = (f"const L = require({json.dumps(str(STATIC / 'listing.js'))}); "
            "const a = JSON.parse(require('fs').readFileSync(0, 'utf8')); "
            f"const v = L[{json.dumps(fn)}]; console.log(JSON.stringify(typeof v === 'function' ? v(...a) : v))")
    return json.loads(subprocess.run([NODE, "-e", code], input=json.dumps(args), capture_output=True, text=True, check=True).stdout)


def topic(article: str, category: str, views: int) -> dict:
    return {"article": article, "category": category, "views": views}


def test_sections_follow_home_order_with_other_last_and_sort_by_views():
    items = [topic("A", "sports", 10), topic("B", OTHER, 900), topic("C", "politics", 5),
             topic("D", "sports", 70), topic("E", "politics", 50)]
    got = listing("sections", items, ORDER, OTHER)
    assert [s["key"] for s in got] == ["politics", "sports", OTHER]          # "Бусад" хамгийн их уншилттай ч сүүлд
    assert [[t["article"] for t in s["topics"]] for s in got] == [["E", "C"], ["D", "A"], ["B"]]


# Нүүрний ангиллын дараалал (app.js-ийн CATS), "Бусад"-гүй
HOME_ORDER = ["politics", "film_tv", "true_crime", "tech_ai", "sports", "music", "games_anime", "celebs", "society", "mongolia"]


@pytest.fixture(scope="module")
def trending() -> list[dict]:
    """Бодит /api/trending-ийн мөрүүд (data/processed + app/model), бүлэглэлтэд хэрэгтэй талбарууд."""
    testclient = pytest.importorskip("fastapi.testclient")
    from app.main import app
    with testclient.TestClient(app) as c:
        items = c.get("/api/trending").json()["items"]
    return [{k: t[k] for k in ("article", "category", "views", "measurable", "fire")} for t in items]


def test_real_topics_make_eleven_sections_with_real_counts_and_about_55_first_rows(trending):
    secs = listing("sections", trending, HOME_ORDER, OTHER)
    assert [s["key"] for s in secs] == [*HOME_ORDER, OTHER]
    n = {s["key"]: len(s["topics"]) for s in secs}
    assert n["politics"] == 16 and n[OTHER] == 150             # "Бүгдийг харах (N)"-ийн N (issue #32)
    # Сэдэв бүр яг нэг хэсэгт
    assert sorted(t["article"] for s in secs for t in s["topics"]) == sorted(t["article"] for t in trending)
    shown = listing("SHOWN")
    assert sum(min(shown, c) for c in n.values()) == 55         # анхны хуудас ~55 мөр (ADR 0013)
    for s in secs:   # хэсгийн эхний мөр = тухайн ангиллын хамгийн их уншигдсан сэдэв
        assert s["topics"][0]["views"] == max(t["views"] for t in trending if t["category"] == s["key"])
