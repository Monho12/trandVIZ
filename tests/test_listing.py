"""app/static/listing.js: "Бүх сэдэв" хуудсыг ангиллаар бүлэглэх (ADR 0013).
Цэвэр функцийг node-оор дуудна (browser-гүй).  pytest -q"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["SHUUGIAN_REFRESH"] = "0"
import node_js  # noqa: E402

ORDER = ["politics", "sports"]   # нүүрний дараалал (app.js-ийн ORDER-ийн жишээ)
OTHER = "Бусад"


def listing(name: str, *args):
    """Listing.<name>(*args)-ийн утга (name нь тогтмол бол түүний утга)."""
    return node_js.call("listing.js", name, *args)


def topic(article: str, category: str, views: int) -> dict:
    return {"article": article, "category": category, "views": views}


def test_sections_follow_home_order_with_other_last_and_sort_by_views():
    items = [topic("A", "sports", 10), topic("B", OTHER, 900), topic("C", "politics", 5),
             topic("D", "sports", 70), topic("E", "politics", 50)]
    got = listing("sections", items, ORDER, OTHER)
    assert [s["key"] for s in got] == ["politics", "sports", OTHER]          # "Бусад" хамгийн их уншилттай ч сүүлд
    assert [[t["article"] for t in s["topics"]] for s in got] == [["E", "C"], ["D", "A"], ["B"]]


def test_equal_views_fall_back_to_article_name_like_the_home_cards():
    """Нүүрний ангиллын карт (src/serve.py) тэнцсэн уншилтыг нэрээр эрэмбэлдэг: хоёр хуудасны эхний мөрүүд зөрөхгүй."""
    items = [topic("B", "sports", 7), topic("C", "sports", 9), topic("A", "sports", 7)]
    got = listing("sections", items, ORDER, OTHER)
    assert [t["article"] for t in got[0]["topics"]] == ["C", "A", "B"]


# Сонгосон 10 ангилал нүүрний дарааллаар (ADR 0013), "Бусад"-гүй. app.js ORDER-оо sections()-д мөн ингэж дамжуулна
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
    # Хэмжигдэх биш сэдэв жагсаалтад үлдэнэ (саарал "цөөн уншилттай" тэмдэгтэй), гэхдээ 🔥 авахгүй (ADR 0004, 0013)
    low = [t for s in secs for t in s["topics"] if not t["measurable"]]
    assert low and not any(t["fire"] for t in low)
