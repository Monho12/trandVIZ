// Сайтын үг ба шошго (ADR 0014): тоо = "уншилт", таамгийн хувь = "анхаарал"; ▲ = өнгөрсөн, ↗/🔥 = таамаг.
// "Өчигдөр" гэдэг үг зөвхөн эндээс, asof = өчигдөр (age_days = 1) үед л гарна; бусад үед огноо ("11/9").
// asof: "YYYY-MM-DD", age: /api/*-ийн age_days (серверийн өнөөдөр, Улаанбаатарын цагаар − asof).
(function (root) {
  const md = (s) => { const [, m, d] = s.split("-"); return `${+m}/${+d}`; };
  const isYesterday = (age) => age === 1;
  const day = (asof, age) => (isYesterday(age) ? "өчигдөр" : md(asof));
  const dayTile = (asof, age) => (isYesterday(age) ? "Өчигдөр" : md(asof));
  const homeTitle = (asof, age) => `${isYesterday(age) ? "Өчигдөр" : md(asof) + "-нд"} дэлхий юуг уншив?`;

  // ▲ шошго: урт "өчигдөр ×3" / "11/8 ×3", богино "×3" (▲ тэмдгийг CSS нэмнэ). Tooltip үргэлж огноотой.
  const surgeText = (ratio, asof, age, short) => (short ? `×${ratio}` : `${day(asof, age)} ×${ratio}`);
  const surgeTip = (ratio, asof) => `${md(asof)}-нд ердийн өдрөөс ${ratio} дахин их уншигдсан`;

  // API-ийн "80%: +10% … +85%" -> "10 удаагийн 8-д: +10% … +85%"
  const interval = (text) => (text ? text.replace(/^80%:\s*/, "10 удаагийн 8-д: ") : "");
  // API-ийн "— (өчигдөр уншилтгүй)" шошгыг хуучирсан өгөгдөлд огноотой болгоно
  const forecastLabel = (label, asof, age) => (isYesterday(age) ? label : label.replace("өчигдөр", `${md(asof)}-нд`));

  // Нүүрний "Ирэх 3 өдөрт юу өсөх вэ?"-ийн тайлбар (PLAN, Нүүр). dates: API-ийн "11/11–11/13", fires: 🔥-ийн тоо,
  // T: 🔥-ийн босго (0.25 -> "25%"), n: API-ийн top_n. "Хэт цөөн уншигддаг..." өгүүлбэрийг app.js tooltip-тэй нь нэмнэ (W.LOW_VIEWS).
  const pctText = (x) => `${Math.round(x * 100)}%`;
  const trendLead = (dates, fires, T, n) => (fires >= 1
    ? `${dates}-нд анхаарал нь хамгийн их өсөх ${n} сэдэв (model-ийн таамаг). 🔥 = ${pctText(T)} ба түүнээс их өсөлт.`
    : `${dates}: онцгой өсөлт (🔥) таамаглагдаагүй. Хамгийн өндөр таамагтай ${n} сэдэв.`);
  // Treemap-ийн хүрээ: n = нийт сэдэв (/api/trending-ийн мөр), m = газрын зурагт орсон (/api/map-ийн мөр)
  const mapScope = (n, m) => `Манай ${n} сэдвээс хамгийн их уншигдсан ${m}, англи Wikipedia.`;
  // "Ангилал бүрт юу уншигдав?"-ийн тайлбар. nCats: картын тоо, perCat: сонгосон сэдэв ÷ ангилал (~15),
  // shown: карт бүрт харуулах сэдэв, reason: "яагаад эдгээр ангилал" (хоосон бол оруулахгүй).
  const catLead = (nCats, perCat, shown, asof, age, reason) => [
    `${nCats} бүлэгт тус бүр ~${Math.round(perCat)} сэдвийг бид гараар сонгосон.`, reason,
    `Карт бүрт ${isYesterday(age) ? "өчигдөр" : md(asof) + "-нд"} хамгийн их уншигдсан ${shown} нь.`,
    "▲ ×2 = ердийн өдрөөс 2 дахин их."].filter(Boolean).join(" ");
  // PLAN-ийн "[Майк бөглөнө: яагаад эдгээр ангилал]". Майк бөглөтөл хоосон (test_words шалгана),
  // "оюутан, залуучуудын сонирхдог" гэж бичихгүй.
  const CAT_REASON = "";
  // Хэмжигдэх сэдвийн босго уншилтаар хөдөлдөг тул тоогүй (ADR 0004)
  const LOW_VIEWS = "Хэт цөөн уншигддаг сэдвийг оруулаагүй.";
  // "Бүх сэдэв"-ийн хэсгийг дэлгэх / хураах товч (сумгүй) ба нүүрний ангиллын картын холбоос (сумтай). n: хэсгийн бодит сэдвийн тоо
  const expand = (n) => `Бүгдийг харах (${n})`;
  const COLLAPSE = "Хураах";
  const seeAll = (n) => `${expand(n)} →`;
  // Хэмжигдэх биш сэдвийн саарал тэмдэг (ADR 0013, 5-р зүйл); tooltip нь TIP.lowViews
  const LOW_TAG = "цөөн уншилттай";
  // "Бусад" хэсгийн гарчгийн доорх 2 мөр (ADR 0013, 7-р зүйл): how = яаж сонгосон (нарийн тоо нь TIP.other, src/fetch_data.py,
  // test_words шалгана), why = яагаад нэмсэн
  const OTHER_NOTE = {
    how: "Wikipedia-ийн сарын топ жагсаалтад 1–2 сар л гараад алга болсон нийтлэлүүд (2021 оноос, жил бүрээс санамсаргүй сонгосон).",
    why: "Сонгосон сэдвүүд ихэвчлэн тогтвортой байдаг тул гэнэт өссөн сэдэв цааш нь үргэлжлэх үү, унтрах уу гэдгийг model сурахын тулд нэмсэн.",
  };

  // "Бүх сэдэв" хуудасны тайлбар (ADR 0013): ▲-ийн өдөр нь asof = өчигдөр үед л "өчигдөр", эрэмбийн өдөр үргэлж огноо.
  const listLead = (asof, age) => "Багана: цэнхэр = бодит уншилт, улаан = ирэх 3 өдрийн таамаг. "
    + `▲ = ${day(asof, age)} ердийнхөөс хэд дахин их. Ангилал бүрт ${md(asof)}-нд хамгийн их уншигдсанаас нь эхлэн.`;

  // ── "Сонирхолтой" хуудас (issue #33). Юуг харуулахыг app/data/make_insights.py сонгоно, энд зөвхөн үг. ──
  const DAYS = ["Да", "Мя", "Лх", "Пү", "Ба", "Бя", "Ня"];                                   // 0 = Даваа
  const DAYS_LONG = ["Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан", "Бямба", "Ням"];
  // r: insights.json-ий ranges-ийн нэг ({from, to}, "YYYY-MM-DD") -> "2026.10.08–2026.11.06"
  const span = (r) => `${r.from.replace(/-/g, ".")}–${r.to.replace(/-/g, ".")}`;
  const year = (iso) => iso.slice(0, 4);
  const factsLead = (r, topics) => `Англи Wikipedia, ${year(r.from)} оноос хойшх өгөгдөл, манай ${topics} сэдэв.`;
  const decayNote = (n) => `Гэнэт шуугисан ${n} сэдвийн дундаж (медиан). Оргил өдрийн уншилт = 100%.`;
  const catsNote = (n, r) => `Бидний сонгосон ${n} сэдвийн дотор, ${span(r)}, англи Wikipedia.`;
  const mongoliaNote = (n, r) => `Англи Wikipedia-ийн уншигчид. Бидний сонгосон ${n} монгол сэдвийн дотор, ${span(r)}.`;
  // names: эхний хоёр ангиллын нэр (их -> бага), views: тэдний уншилт. Зөрүү 5%-иас бага бол "бараг тэнцүү"
  const TIE = 0.05;
  const catsHeadline = ([a, b], [va, vb]) => ((va - vb) / va < TIE ? `${a} ба ${b} бараг тэнцүү` : `${a} хамгийн их уншигдсан`);
  // picks: insights.json-ий weekday_pick ([{key, peak}], peak: 0 = Даваа), names: {key: нэр}.
  // Оргил гараг ижил бол нэг өгүүлбэрт нэгтгэнэ, үгүй бол долоо хоногийн дарааллаар.
  const MOST = "хамгийн их уншигддаг";
  const weekdayTitle = (picks, names) => {
    const [a, b] = picks;
    if (a.peak === b.peak) return `${names[a.key]} ба ${names[b.key]} хоёулаа ${DAYS_LONG[a.peak]} гарагт ${MOST}`;
    return [...picks].sort((x, y) => x.peak - y.peak).map((p) => `${names[p.key]} ${DAYS_LONG[p.peak]} гарагт`).join(", ") + ` ${MOST}`;
  };
  // index: 100 = долоо хоногийн дундаж -> "Пү +10%", "Ня −15%"
  const weekdayLabel = (dow, index) => {
    const p = Math.round(index - 100);
    return `${DAYS[dow]} ${p > 0 ? "+" : p < 0 ? "−" : ""}${Math.abs(p)}%`;
  };
  const WEEKDAY_NOTE = "Долоо хоногийн дунджаас хэдэн хувиар их/бага уншигддаг вэ. Хамгийн тод ялгаатай 2 ангилал.";
  const HOLIDAY_TITLE = "Баярууд жил бүр яг нэг сардаа оргилдог";
  // month: "YYYY-MM" (сүүлийн бүтэн жилийн оргил сар)
  const holidayLabel = (name, month) => `${name} · ${+month.slice(5)}-р сар`;
  // incompleteYear: 12 сар нь бүрдээгүй сүүлийн жил (байхгүй бол null)
  const holidayNote = (r, incompleteYear) => `Сар бүрийн өдрийн дундаж уншилт, ${year(r.from)} оноос.`
    + (incompleteYear ? ` ${incompleteYear} он дуусаагүй.` : "");

  const TIP = {
    attention: "Анхаарал: Wikipedia-ийн нийт уншилтад эзлэх хувь",
    interval: "80% интервал: model-ийн өмнөх алдаанаас тооцсон хүрээ",
    normal: "ердийн түвшин (медиан): сүүлийн 2 сарын уншилт, сүүлийн 7 хоногийг оруулаагүй",
    forecastBar: "таамагласан уншилт (Wikipedia-ийн нийт уншилт өөрчлөгдөхгүй гэж үзвэл)",
    lowViews: "сүүлийн 7 хоногт Wikipedia-ийн сая уншилт тутмаас дунджаар 1-ээс бага",
    table: "Доод–Дээд: 10 удаагийн 8-д бодит тоо энэ хооронд байдаг (80% интервал).",
    other: "Сарын шилдэг 200-д 1–2 сар орсон, оргил өдөр нь ердийнхөөсөө 8+ дахин их",
  };

  const Words = { md, day, dayTile, homeTitle, surgeText, surgeTip, interval, forecastLabel, trendLead, mapScope, catLead, CAT_REASON, seeAll, expand, COLLAPSE,
    listLead, LOW_TAG, OTHER_NOTE, LOW_VIEWS, TIP,
    DAYS, span, factsLead, decayNote, catsNote, mongoliaNote, catsHeadline, weekdayTitle, weekdayLabel, WEEKDAY_NOTE,
    HOLIDAY_TITLE, holidayLabel, holidayNote };
  if (typeof module !== "undefined" && module.exports) module.exports = Words;
  else root.Words = Words;
})(typeof window !== "undefined" ? window : globalThis);
