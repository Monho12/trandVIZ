"""Загвар хуудасны үг (issue #34, PLAN "Загвар"): багш, оюутанд ойлгомжтой, дотоод шошгогүй, тоо ба огноо /api/model-оос.
words.js-ийн цэвэр функцийг node-оор, жинхэнэ /api/model-ийн хариу дээр дуудна.  pytest -q"""
import copy
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["SHUUGIAN_REFRESH"] = "0"
import node_js  # noqa: E402

fastapi_testclient = pytest.importorskip("fastapi.testclient")


def words(name: str, *args):
    return node_js.call("words.js", name, *args)


def test_log_mae_converts_to_percent_error_like_the_rest_of_the_page():
    """exp(MAE) − 1, хувиар (src/evaluate.py: mae_as_pct_error). Гараар: exp(0.1912) = 1.21070, exp(0.1826) = 1.20033."""
    assert words("maePct", 0.1912) == pytest.approx(21.070, abs=0.001)
    assert words("maePct", 0.1826) == pytest.approx(20.033, abs=0.001)
    assert words("maePct", 0) == 0


def test_period_length_in_whole_months():
    assert words("months", "2025-07-01", "2026-03-31") == 9      # validation
    assert words("months", "2026-04-01", "2026-11-03") == 7      # test
    assert words("months", "2026-01-01", "2026-12-31") == 12


@pytest.fixture(scope="module")
def api_model() -> dict:
    from app.main import app
    with fastapi_testclient.TestClient(app) as c:
        return c.get("/api/model").json()


@pytest.fixture(scope="module")
def page(api_model) -> dict:
    return words("modelWords", api_model)


def texts(v) -> list[str]:
    """Хуудсанд гарах бүх мөр (dict / list-ийн навчнууд), хуудасны дарааллаар."""
    if isinstance(v, str):
        return [v]
    return [s for x in (v.values() if isinstance(v, dict) else v) for s in texts(x)]


def sentences(text: str) -> int:
    """Өгүүлбэрийн тоо: цэг/асуултын тэмдгийн ард зай эсвэл төгсгөл ("2026.04.01", "3 000" тоологдохгүй)."""
    return len(re.findall(r"[.?!](?=\s|$)", text))


def test_pipeline_has_eight_steps_in_order(page):
    assert [s["title"] for s in page["steps"]] == ["Цуглуулах", "Цэвэрлэх", "Feature", "Хуваах", "Сургах", "Сонгох", "Шалгах", "Вэб"]


def test_no_internal_group_labels_anywhere(page):
    for s in texts(page):
        assert not re.search(r"\((а|б|в)\)", s), s
        assert "вирал" not in s.lower(), s
        assert "шалгалтын үед гэнэт шуугисан" not in s.lower(), s


def test_jargon_is_never_left_unexplained(page):
    """"valid" гэсэн товчлол байхгүй; purge, horizon, trial нь зөвхөн монгол үгийн ард хаалтанд."""
    for s in texts(page):
        assert not re.search(r"\bvalid\b", s, re.I), s
        for word in ("purge", "horizon", "trial"):
            assert len(re.findall(word, s, re.I)) == len(re.findall(rf"\({word}\b", s, re.I)), s
    joined = " ".join(texts(page))
    for gloss in ("оролдлого (trial", "(horizon)", "(purge)", "тэгш хэмтэй мод (symmetric trees)", "дундаж алдаа (MAE)", "(skill score)"):
        assert gloss in joined, gloss
    # validation: хуудсанд анх гарахдаа тайлбартай
    assert re.search(r"validation", joined, re.I).start() == joined.find("Validation (сургалтад ороогүй шалгах өгөгдөл)")


def test_the_36_topics_have_one_name_everywhere(page):
    mentions = [s for s in texts(page) if "36 сэдв" in s]
    assert len(mentions) >= 3
    for s in mentions:
        assert len(re.findall("36 сэдв", s)) == len(re.findall("сургалтын дараа гэнэт шуугисан 36 сэдв", s, re.I)), s


def test_card_line_is_short_and_detail_is_at_most_three_sentences(page):
    for s in page["steps"]:
        assert 1 <= sentences(s["line"] + ".") <= 2 and len(s["line"]) <= 60, s["line"]
        extra = 1 if s["title"] == "Сонгох" else 0      # + "Яагаад CatBoost?" руу заасан холбоос өгүүлбэр
        assert 2 <= sentences(s["more"]) <= 3 + extra, s["more"]
    choose = page["steps"][5]["more"]
    assert choose.endswith('доорх "Яагаад CatBoost?" хэсгийг үзнэ үү.')


def test_overfit_note_shows_percent_with_units_and_the_log_mae(page, api_model):
    assert api_model["pipeline"]["naive_h3"] == {"train": 0.1912, "valid": 0.1826}
    assert "дунджаар 21.1% → 20.0% зөрсөн (лог MAE 0.191 → 0.183)" in page["overfitNote"]
    assert "тэр 9 сар илүү тайван" in page["overfitNote"]


def test_main_chart_hint_names_test_period_and_chosen_topics(page):
    assert page["errHint"].startswith(
        "Дунджаар хэдэн хувиар зөрдөг вэ (2026.04.01–2026.11.03, model огт хараагүй 7 сарын test өгөгдөл, бидний сонгосон 151 сэдэв).")


def test_step_text_follows_the_plan(page):
    by = {s["title"]: s for s in page["steps"]}
    assert by["Цуглуулах"]["more"].count("301 сэдэв = бидний сонгосон 151 + гэнэт шуугисан 150.") == 1
    assert by["Цэвэрлэх"]["line"] == "Bot-ийн үсрэлт, хоосон өдрүүдийг зассан"
    assert by["Хуваах"]["line"] == "Сургах, сонгох, шалгах гурван үе"
    assert "сургах (train, 2025.06 хүртэл), сонгох (validation, 2026.03 хүртэл), эцэст нь шалгах (test, 2026.11 хүртэл)" in by["Хуваах"]["more"]
    assert by["Сургах"]["line"] == "3 алгоритм × 3 өдөр × 25 оролдлого" and by["Сургах"]["unit"] == "оролдлого (trial)"
    assert "LightGBM, XGBoost, CatBoost гурвыг 1, 2, 3 өдрийн дараах таамаг (horizon)" in by["Сургах"]["more"]
    assert by["Сонгох"]["line"] == "Validation дээр хамгийн бага алдсан"
    assert "сургалтад ороогүй 9 сарын өгөгдөл (validation)" in by["Сонгох"]["more"]
    assert "(2026.04.01–2026.11.03, model огт хараагүй 7 сар)" in by["Шалгах"]["more"]
    assert '"20% бага алдаа" = энгийн аргаас хэдэн хувь бага алдсан (skill score).' in by["Шалгах"]["more"]
    assert "CatBoost model-оор ирэх 3 өдрийг таамаглана" in by["Вэб"]["more"]


def test_numbers_and_dates_come_from_the_api_not_the_code(api_model):
    m = copy.deepcopy(api_model)
    p = m["pipeline"]
    p.update(topics=310, topics_main=160, topics_groups={"а": 160, "б": 110, "в": 40}, train_end="2025-08-31",
             valid_end="2026-02-28", test_start="2026-03-01", end="2026-12-05", n_trials=30, horizons=2, n_algos=2,
             algo_name="XGBoost", skill_h3=17.6, naive_h3={"train": 0.3, "valid": 0.1})
    joined = " ".join(texts(words("modelWords", m)))
    for want in ("310 сэдэв = бидний сонгосон 160 + гэнэт шуугисан 150", "сургалтын дараа гэнэт шуугисан 40 сэдв",
                 "train, 2025.08 хүртэл", "validation, 2026.02 хүртэл", "test, 2026.12 хүртэл", "2 алгоритм × 2 өдөр × 30 оролдлого",
                 "2026.03.01–2026.12.05, model огт хараагүй 9 сарын test", "сургалтад ороогүй 6 сарын өгөгдөл",
                 '"18% бага алдаа"', "35.0% → 10.5% зөрсөн (лог MAE 0.300 → 0.100)", "(trial, 30 × 2)", 'Яагаад XGBoost?'):
        assert want in joined, want
    for stale in ("36 сэдв", "151", "2025.06", "CatBoost model"):
        assert stale not in joined, stale
