"""Төвийг сахисан үг (ADR 0022, issue #45): англи Wikipedia-г "дэлхий" гэж нэрлэхгүй, "сонирхол", "хандалт" гэхгүй.
Нүүрний бүтцээс хамааралгүй газрууд: <title>, meta/og, "Загвар" хуудасны h1, README-ийн танилцуулга.  pytest -q"""
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["SHUUGIAN_REFRESH"] = "0"
import node_js  # noqa: E402

fastapi_testclient = pytest.importorskip("fastapi.testclient")

ROOT = Path(__file__).resolve().parents[1]
BANNED = ("дэлхий", "сонирх", "хандалт")       # CONTEXT.md-ийн _Зайлсхийх_

TITLE = "Шуугиан — англи Wikipedia-д юу огцом уншигдав"
DESCRIPTION = ("Англи Wikipedia-ийн өдөр тутмын уншилтаас огцом өссөн сэдвийг олж, "
               "ирэх 3 өдөрт үргэлжлэх үү, унтрах уу гэдгийг таамагладаг.")


def assert_neutral(text: str, where: str):
    for bad in BANNED:
        assert bad not in text.lower(), f"{where}: '{bad}'"


class Head(HTMLParser):
    """<title>-ийн текст ба <meta name|property> → content."""
    def __init__(self):
        super().__init__()
        self.title, self.meta, self._in_title = "", {}, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and ("name" in a or "property" in a):
            self.meta[a.get("name") or a["property"]] = a.get("content")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with fastapi_testclient.TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def head(client) -> Head:
    h = Head()
    h.feed(client.get("/").text)
    return h


def test_page_title_and_description_name_english_wikipedia(head):
    assert head.title == TITLE
    assert head.meta["description"] == DESCRIPTION


def test_share_preview_repeats_title_and_description_not_the_daily_h1(head):
    """og:* нь тогтвортой: өдөр бүр өөрчлөгддөг нүүрний h1 (огноо, тоо)-ээс тусдаа (ADR 0022)."""
    assert head.meta["og:title"] == TITLE
    assert head.meta["og:description"] == DESCRIPTION


def test_head_has_no_banned_words(head):
    for where, text in [("<title>", head.title), *head.meta.items()]:
        assert_neutral(text or "", where)
    assert "Шуугиан" in head.title       # брэнд хэвээр


def test_model_page_h1_asks_how_right_past_forecasts_were(client):
    """h1-д "загвар" үг үлдээхгүй; "байсан": track record бол өнгөрсөн өгөгдөл (ADR 0027)."""
    title = node_js.call("words.js", "modelWords", client.get("/api/model").json())["title"]
    assert title == "Таамаг өмнө нь хэр зөв байсан бэ?"
    assert "загвар" not in title.lower()
    assert_neutral(title, "Загвар хуудасны h1")


def test_readme_intro_names_english_wikipedia_and_attention():
    """README-ийн h1 ба танилцуулга (эхний "## "-ээс өмнөх хэсэг)."""
    intro = (ROOT / "README.md").read_text(encoding="utf-8").split("\n## ", 1)[0]
    flat = re.sub(r"\s+", " ", intro)
    assert intro.startswith(f"# {TITLE}\n")
    assert "уншилтаар англи Wikipedia-ийн анхаарлыг" in flat
    assert "ирэх 3 өдрийн** анхаарлыг" in flat
    assert_neutral(intro, "README-ийн танилцуулга")
