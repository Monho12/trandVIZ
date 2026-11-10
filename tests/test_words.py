"""app/static/words.js: сайтын үг ба шошго (ADR 0014). ▲ = өнгөрсөн, "өчигдөр" зөвхөн asof = өчигдөр үед.
Цэвэр функцүүдийг node-оор дуудна (browser-гүй).  pytest -q"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import node_js  # noqa: E402
from src import scoring  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STATIC = node_js.STATIC
ASOF = "2026-11-09"   # сайтын огнооны формат: "11/9"


def words(name: str, *args):
    """Words.<name>(*args)-ийн утга (name нь тогтмол бол түүний утга)."""
    return node_js.call("words.js", name, *args)


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


def test_list_lead_explains_the_bars_and_names_the_asof_date():
    assert words("listLead", ASOF, 1) == (
        "Багана: цэнхэр = бодит уншилт, улаан = ирэх 3 өдрийн таамаг. ▲ = өчигдөр ердийнхөөс хэд дахин их. "
        "Ангилал бүрт 11/9-нд хамгийн их уншигдсанаас нь эхлэн.")
    stale = words("listLead", ASOF, 4)       # хуучирсан өгөгдөл: "өчигдөр" гэж хэлэхгүй
    assert "▲ = 11/9 ердийнхөөс хэд дахин их." in stale and "өчигдөр" not in stale


def test_expand_button_text_has_the_count_and_no_arrow():
    assert words("expand", 150) == "Бүгдийг харах (150)"      # товч: холбоос биш тул сумгүй
    assert words("seeAll", 150) == "Бүгдийг харах (150) →"


def test_other_section_note_agrees_with_how_viral_topics_were_picked():
    """ "Бусад" хэсгийн 2 мөр тайлбар ба tooltip-ийн тоо src/fetch_data.py-тай таарна (ADR 0013, 7-р зүйл)."""
    from src import fetch_data
    note, tip = words("OTHER_NOTE"), words("TIP")["other"]
    assert set(note) == {"how", "why"} and f"{fetch_data.START.year} оноос" in note["how"]
    assert f"оргил өдөр нь ердийнхөөсөө {fetch_data.VIRAL_MIN_RATIO}+ дахин их" in tip
    shown = " ".join([note["how"], note["why"], tip]).lower()
    assert "viral" not in shown and "вирал" not in shown   # ADR 0005


# ── "Сонирхолтой" хуудас (issue #33): гарчиг, саарал мөр, огнооны хүрээ ──
NAMES = {"tech_ai": "AI", "sports": "Спорт"}


def test_weekday_title_names_each_category_with_its_peak_day_in_week_order():
    picks = [{"key": "sports", "peak": 6, "low": 4}, {"key": "tech_ai", "peak": 3, "low": 6}]   # хэлбэлзлээр эрэмбэлсэн
    assert words("weekdayTitle", picks, NAMES) == "AI Пүрэв гарагт, Спорт Ням гарагт хамгийн их уншигддаг"


def test_weekday_title_when_both_categories_peak_on_the_same_day():
    picks = [{"key": "sports", "peak": 3, "low": 4}, {"key": "tech_ai", "peak": 3, "low": 6}]
    assert words("weekdayTitle", picks, NAMES) == "Спорт ба AI хоёулаа Пүрэв гарагт хамгийн их уншигддаг"


def test_weekday_bar_labels_are_percent_above_or_below_the_weekly_mean():
    assert words("weekdayLabel", 3, 109.8) == "Пү +10%"
    assert words("weekdayLabel", 6, 85.3) == "Ня −15%"      # хасах тэмдэг (−), зураас (-) биш
    assert words("weekdayLabel", 0, 100.2) == "Да 0%"


def test_categories_headline_calls_a_gap_under_five_percent_a_tie():
    assert words("catsHeadline", ["Улс төр", "AI"], [6146448, 6108244]) == "Улс төр ба AI бараг тэнцүү"
    assert words("catsHeadline", ["Улс төр", "AI"], [100, 95.1]) == "Улс төр ба AI бараг тэнцүү"
    assert words("catsHeadline", ["Улс төр", "AI"], [100, 95]) == "Улс төр хамгийн их уншигдсан"   # яг 5% бол тэнцүү биш


def test_scope_notes_show_the_real_date_range_and_counts():
    r30 = {"from": "2026-10-08", "to": "2026-11-06"}
    assert words("span", r30) == "2026.10.08–2026.11.06"
    assert words("factsLead", {"from": "2021-01-01", "to": "2026-11-06"}, 301) == "Англи Wikipedia, 2021 оноос хойшх өгөгдөл, манай 301 сэдэв."
    assert words("decayNote", 146) == "Гэнэт шуугисан 146 сэдвийн дундаж (медиан). Оргил өдрийн уншилт = 100%."
    assert words("catsNote", 151, r30) == "Бидний сонгосон 151 сэдвийн дотор, 2026.10.08–2026.11.06, англи Wikipedia."
    assert words("mongoliaNote", 15, {"from": "2025-11-07", "to": "2026-11-06"}) == (
        "Англи Wikipedia-ийн уншигчид. Бидний сонгосон 15 монгол сэдвийн дотор, 2025.11.07–2026.11.06.")
    assert words("WEEKDAY_NOTE") == "Долоо хоногийн дунджаас хэдэн хувиар их/бага уншигддаг вэ. Хамгийн тод ялгаатай 2 ангилал."


def test_holiday_note_mentions_the_unfinished_year_only_when_there_is_one():
    r = {"from": "2023-01-01", "to": "2026-11-06"}
    assert words("holidayNote", r, 2026) == "Сар бүрийн өдрийн дундаж уншилт, 2023 оноос. 2026 он дуусаагүй."
    assert words("holidayNote", r, None) == "Сар бүрийн өдрийн дундаж уншилт, 2023 оноос."
    assert words("HOLIDAY_TITLE") == "Баярууд жил бүр яг нэг сардаа оргилдог"
    assert words("holidayLabel", "Зул сар", "2025-12") == "Зул сар · 12-р сар"
    assert words("holidayLabel", "Валентин", "2025-02") == "Валентин · 2-р сар"


def test_facts_page_has_no_stale_window_words_or_red():
    """Хүрээг файлаас уншина: "сүүлийн 30 хоног / 1 жил / 5 жил" гэж гараар бичихгүй; графикт улаан үгүй."""
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    facts = js[js.index("async function facts()"):js.index("// ═════════ Router")]
    for stale in ("сүүлийн 30", "1 жил", "5 жил", "таамаглахад амар", "#e63946", "Ажлын өдөр"):
        assert stale not in facts, stale
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    line_rules = "\n".join(ln for ln in css.splitlines() if ".l-c" in ln)
    assert line_rules and not re.search(r"#e63946|#b5222e", line_rules)
