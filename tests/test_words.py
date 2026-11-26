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
ASOF = "2026-11-09"   # сайтын огноо (ADR 0018): өгүүлбэрт "11-р сарын 9", карт/тэнхлэгт "11.09"


def words(name: str, *args):
    """Words.<name>(*args)-ийн утга (name нь тогтмол бол түүний утга)."""
    return node_js.call("words.js", name, *args)


def test_short_date_is_month_dot_day_zero_padded():
    """Карт, графикийн тэнхлэг, шошго (ADR 0018): "11.09", "11/9" биш."""
    assert words("md", ASOF) == "11.09"
    assert words("md", "2026-01-05") == "01.05"
    assert words("md", "2026-12-31") == "12.31"


def test_long_date_for_sentences_names_the_month_and_adds_the_year_only_when_it_differs():
    """Өгүүлбэр, tooltip, гарчиг (ADR 0018): "11-р сарын 9"; жил нь ref-ийнхээс өөр бол "2025 оны 11-р сарын 9"."""
    assert words("longDate", ASOF) == "11-р сарын 9"
    assert words("longDate", "2026-01-05") == "1-р сарын 5"
    assert words("longDate", ASOF, "2026-11-12") == "11-р сарын 9"
    assert words("longDate", "2025-12-31", "2026-01-02") == "2025 оны 12-р сарын 31"
    assert words("longDate", "2027-01-01", "2026-12-31") == "2027 оны 1-р сарын 1"
    assert words("longDate", "2026-11-10T03:15:00+08:00") == "11-р сарын 10"    # /api/model-ийн trained_at






def topic(ratio=3, views_ratio=2.8, typical_pct=0.08, similar_days=0):
    return {"ratio": ratio, "views_ratio": views_ratio, "typical_pct": typical_pct, "similar_days": similar_days}


def test_surge_tooltip_has_date_attention_ratio_raw_views_in_brackets_and_frequency():
    """ADR 0017: "Тайлбар нь давтамжаар", z тоог харуулахгүй. CONTEXT.md: анхаарлын харьцааны хажууд түүхий уншилтын харьцаа хаалтанд.
    Tooltip-ийн огноо өгүүлбэрийн хэлбэрээр (ADR 0018)."""
    assert words("surgeTip", topic(), ASOF) == (
        "11-р сарын 9-нд анхаарал ердийн өдрөөс 3 дахин их (уншилт ×2.8). "
        "Энэ сэдэв ихэвчлэн ±8%-иар л хэлбэлздэг. Сүүлийн 2 сард ийм өдөр нэг ч удаа гараагүй.")
    assert words("surgeTip", topic(ratio=1.9, views_ratio=2.1, typical_pct=0.184, similar_days=3), ASOF) == (
        "11-р сарын 9-нд анхаарал ердийн өдрөөс 1.9 дахин их (уншилт ×2.1). "
        "Энэ сэдэв ихэвчлэн ±18%-иар л хэлбэлздэг. Сүүлийн 2 сард ийм өдөр 3 удаа гарсан.")


def test_surge_tooltip_skips_raw_views_ratio_when_unknown():
    tip = words("surgeTip", topic(views_ratio=None), ASOF)
    assert tip.startswith("11-р сарын 9-нд анхаарал ердийн өдрөөс 3 дахин их. Энэ сэдэв") and "уншилт ×" not in tip




def test_day_word_for_titles_and_tiles():
    assert words("day", ASOF, 1) == "өчигдөр"
    assert words("day", ASOF, 3) == "11.09"
    assert words("dayTile", ASOF, 1) == "Өчигдөр"
    assert words("dayTile", ASOF, 3) == "11.09"


def test_interval_reads_as_8_of_10_times():
    assert words("interval", "80%: +10% … +85%") == "10 удаагийн 8-д: +10% … +85%"
    assert words("interval", "") == ""     # x_0 = 0: интервал тодорхойгүй


def test_no_views_label_does_not_hardcode_yesterday():
    na = scoring.LABEL_NA                   # "— (өчигдөр уншилтгүй)": API хэвээр
    assert words("forecastLabel", na, ASOF, 1) == na
    assert words("forecastLabel", na, ASOF, 4) == "— (11.09-нд уншилтгүй)"
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
    facts = js[js.index("async function facts("):js.index("// ═════════ Router")]
    for stale in ("сүүлийн 30", "1 жил", "5 жил", "таамаглахад амар", "#e63946", "Ажлын өдөр"):
        assert stale not in facts, stale
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    line_rules = "\n".join(ln for ln in css.splitlines() if ".l-c" in ln)
    assert line_rules and not re.search(r"#e63946|#b5222e", line_rules)


# ── ADR 0018: сайтад "11/9" маягийн налуу зураастай огноо үлдээгүй, огноо бүр words.js-ээр дамжина ──
SLASH_DATE = re.compile(r"(?<![\d/])\d{1,2}/\d{1,2}(?![\d/])|\$\{[^}]*\}/\$\{")   # "11/9", "11/11–11/13", `${m}/${d}`


def test_static_files_have_no_slash_dates():
    for f in [*STATIC.glob("*.js"), *STATIC.glob("*.html"), *STATIC.glob("*.css")]:
        hits = SLASH_DATE.findall(f.read_text(encoding="utf-8"))
        assert not hits, f"{f.name}: {hits}"


def test_only_words_js_formats_dates():
    """charts.js, app.js нь огноог өөрсдөө задалж, бичихгүй: Words.md / Words.longDate / Words.span-ийг дуудна."""
    own = re.compile(r'split\("-"\)|сарын|-р сар|padStart|getMonth|getDate|toLocale(Date)?String|\.slice\(5')
    for f in STATIC.glob("*.js"):
        if f.name == "words.js":
            continue
        code = re.sub(r"/\*.*?\*/|(?<!:)//[^\n]*", "", f.read_text(encoding="utf-8"), flags=re.S)   # тайлбарыг алгасна
        hits = [m.group(0) for m in own.finditer(code)]
        assert not hits, f"{f.name}: огноог өөрөө бичсэн {hits}"


def test_insights_text_has_no_slash_dates():
    text = (ROOT / "app" / "data" / "insights.json").read_text(encoding="utf-8")
    assert not SLASH_DATE.findall(text)
