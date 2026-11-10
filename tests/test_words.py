"""app/static/words.js: сайтын үг ба шошго (ADR 0014). ▲ = өнгөрсөн, "өчигдөр" зөвхөн asof = өчигдөр үед.
Цэвэр функцүүдийг node-оор дуудна (browser-гүй).  pytest -q"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import scoring  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
NODE = shutil.which("node")
ASOF = "2026-11-09"   # сайтын огнооны формат: "11/9"


def words(fn: str, *args):
    """Words.<fn>(*args)-ийн утга (fn нь тогтмол бол түүний утга)."""
    if NODE is None:
        pytest.skip("node алга")
    code = f"const W = require({json.dumps(str(STATIC / 'words.js'))}); const v = W[{json.dumps(fn)}]; console.log(JSON.stringify(typeof v === 'function' ? v(...{json.dumps(args)}) : v))"
    return json.loads(subprocess.run([NODE, "-e", code], capture_output=True, text=True, check=True).stdout)


def test_surge_label_says_yesterday_only_when_asof_is_yesterday():
    assert words("surgeText", 3, ASOF, 1) == "өчигдөр ×3"
    assert words("surgeText", 3, ASOF, 4) == "11/9 ×3"       # хуучирсан өгөгдөл: огноо
    assert words("surgeText", 3, ASOF, 0) == "11/9 ×3"       # asof = өнөөдөр ч "өчигдөр" биш
    assert words("surgeText", 2.4, "2026-01-05", 2) == "1/5 ×2.4"


def test_short_surge_label_has_no_day():
    assert words("surgeText", 3, ASOF, 1, True) == "×3"
    assert words("surgeText", 3, ASOF, 4, True) == "×3"


def test_surge_tooltip_always_has_the_date():
    assert words("surgeTip", 3, ASOF) == "11/9-нд ердийн өдрөөс 3 дахин их уншигдсан"


def test_day_word_for_titles_and_tiles():
    assert words("day", ASOF, 1) == "өчигдөр"
    assert words("day", ASOF, 3) == "11/9"
    assert words("dayTile", ASOF, 1) == "Өчигдөр"
    assert words("dayTile", ASOF, 3) == "11/9"
    assert words("homeTitle", ASOF, 1) == "Өчигдөр дэлхий юуг уншив?"
    assert words("homeTitle", ASOF, 3) == "11/9-нд дэлхий юуг уншив?"


def test_interval_reads_as_8_of_10_times():
    assert words("interval", "80%: +10% … +85%") == "10 удаагийн 8-д: +10% … +85%"
    assert words("interval", "") == ""     # x_0 = 0: интервал тодорхойгүй


def test_no_views_label_does_not_hardcode_yesterday():
    na = scoring.LABEL_NA                   # "— (өчигдөр уншилтгүй)": API хэвээр
    assert words("forecastLabel", na, ASOF, 1) == na
    assert words("forecastLabel", na, ASOF, 4) == "— (11/9-нд уншилтгүй)"
    assert words("forecastLabel", "🔥 +35%", ASOF, 4) == "🔥 +35%"


def test_static_files_have_no_banned_words_or_old_colour_name():
    for f in [*STATIC.glob("*.js"), *STATIC.glob("*.css"), *STATIC.glob("*.html")]:
        text = f.read_text(encoding="utf-8")
        assert "orange" not in text, f"{f.name}: --orange -> --forecast"
        for bad in ("хандалт", "улбар шар", "хэвийн"):
            assert bad not in text.lower(), f"{f.name}: '{bad}'"
        # "өчигдөр" зөвхөн words.js-ээр (asof = өчигдөр үед л) гарна
        if f.name != "words.js":
            assert not re.search(r"[өӨ]чигд[өр]", text), f"{f.name}: 'өчигдөр'-ийг хатуу бичсэн"
    assert "--forecast: #e63946" in (STATIC / "styles.css").read_text(encoding="utf-8")


DATES = "11/11–11/13"


def test_trend_lead_with_fires_names_dates_and_threshold_in_percent():
    s = words("trendLead", DATES, 3, 0.25, 10)
    assert s == ("11/11–11/13-нд анхаарал нь хамгийн их өсөх 10 сэдэв (model-ийн таамаг). "
                 "🔥 = 25% ба түүнээс их өсөлт.")
    assert "0.25" not in s
    assert words("trendLead", DATES, 1, 0.3, 8).startswith("11/11–11/13-нд анхаарал нь хамгийн их өсөх 8 сэдэв")
    assert "🔥 = 30% ба" in words("trendLead", DATES, 1, 0.3, 8)


def test_trend_lead_without_fires_does_not_mention_a_threshold():
    s = words("trendLead", DATES, 0, 0.25, 10)
    assert s == "11/11–11/13: онцгой өсөлт (🔥) таамаглагдаагүй. Хамгийн өндөр таамагтай 10 сэдэв."
    assert "ба түүнээс их" not in s and "хамгийн их өсөх" not in s


def test_map_scope_names_both_counts():
    assert words("mapScope", 301, 40) == "Манай 301 сэдвээс хамгийн их уншигдсан 40, англи Wikipedia."


def test_category_lead_counts_from_data_and_skips_empty_reason():
    assert words("catLead", 10, 15.1, 4, ASOF, 1, "") == (
        "10 бүлэгт тус бүр ~15 сэдвийг бид гараар сонгосон. Карт бүрт өчигдөр хамгийн их уншигдсан 4 нь. "
        "▲ ×2 = ердийн өдрөөс 2 дахин их.")
    assert words("catLead", 9, 14.6, 3, ASOF, 4, "Учир нь X.") == (
        "9 бүлэгт тус бүр ~15 сэдвийг бид гараар сонгосон. Учир нь X. Карт бүрт 11/9-нд хамгийн их уншигдсан 3 нь. "
        "▲ ×2 = ердийн өдрөөс 2 дахин их.")


def test_category_reason_stays_out_until_mike_fills_it_in_plan():
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    reason = words("CAT_REASON")
    if "[Майк бөглөнө" in plan:
        assert reason == ""
    else:
        assert reason and reason in plan


def test_see_all_link_text():
    assert words("seeAll", 16) == "Бүгдийг харах (16) →"
