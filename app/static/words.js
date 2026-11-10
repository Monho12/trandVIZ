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

  // ── "Загвар" хуудас (issue #34, PLAN "Загвар"). Уншигч: ADR уншаагүй багш, оюутан. Дотоод шошго ((а)/(б)/(в), valid) байхгүй,
  // мэргэжлийн үг англиар, анх гарахдаа тайлбартай. Бүх тоо, огноо /api/model-оос (m). Буцаах мөрүүд энгийн текст (HTML биш),
  // талбаруудын дараалал = хуудасны дараалал (test_model_words "анх гарахад"-ыг үүгээр шалгана). ──
  const num = (v) => Number(v).toLocaleString("en-US").replace(/,/g, " ");
  // Лог MAE -> "дунджаар хэдэн хувиар зөрдөг вэ": exp(MAE) − 1 (src/evaluate.py: mae_as_pct_error-той ижил)
  const maePct = (maeLog) => Math.expm1(maeLog) * 100;
  // Хоёр огнооны хоорондох хугацаа сараар, бүхэл рүү дөхүүлсэн: "9 сарын validation", "7 сарын test"
  const months = (from, to) => Math.round((Date.parse(to) - Date.parse(from)) / 864e5 / 30.4375);
  const modelWords = (m) => {
    const p = m.pipeline, N = m.names, naive = `"${N.naive}"`;
    const ym = (iso) => iso.slice(0, 7).replace("-", ".");
    const testSpan = span({ from: p.test_start, to: p.end }), testMonths = months(p.test_start, p.end);
    const validMonths = months(p.train_end, p.valid_end);
    const chosen = `бидний сонгосон ${p.topics_main} сэдэв`;
    const after = `сургалтын дараа гэнэт шуугисан ${p.topics_groups["в"]} сэдвийг`;   // хуудас даяар энэ л нэр
    const After = after[0].toUpperCase() + after.slice(1);
    const algos = m.valid.algos.map((a) => N[a]).join(", ");
    const days = Array.from({ length: p.horizons }, (_, i) => i + 1).join(", ");
    const skill = Math.round(p.skill_h3);
    const steps = [
      ["Цуглуулах", num(p.topics), "сэдэв", `Wikipedia-ийн өдөр тутмын уншилт, ${p.years} жил`,
        `Англи Wikipedia-ийн ${span({ from: p.start, to: p.end })} хоорондох өдөр тутмын уншилтыг Wikimedia-ийн нээлттэй API-аас татсан, зөвхөн хүний (bot биш). `
        + `${p.topics} сэдэв = бидний сонгосон ${p.topics_main} + гэнэт шуугисан ${p.topics - p.topics_main}. `
        + "Анхаарлыг (нийтэд эзлэх хувь) тооцохын тулд Wikipedia-ийн өдрийн нийт уншилтыг ч татсан."],
      ["Цэвэрлэх", num(Math.round(p.clean_rows / 1000)), "мянган мөр", "Bot-ийн үсрэлт, хоосон өдрүүдийг зассан",
        "Ганцхан өдөр огцом үсрээд буцсан тоог (ихэвчлэн bot) хязгаарласан. "
        + "Сэдэв идэвхтэй болохоос өмнөх хоосон өдрүүдийг хассан (хаанаас эхлэхийг зөвхөн өнгөрсөн өгөгдлөөр шийдсэн). "
        + "Эцэст нь уншилтыг тухайн өдрийн нийт уншилтад хувааж анхаарал болгосон: 300 сая уншилтаас 3 000 нь энэ сэдэвт бол анхаарал = 10."],
      ["Feature", num(p.n_features), "feature", "Өсөлт, савлагаа, гараг, улирал",
        'Feature = model-д өгдөг тоо, жишээ нь "өчигдрөөс хэр өссөн", "сүүлийн 7 хоногийн савлагаа". '
        + "Бүгдийг зөвхөн өнгөрсөн өдрүүдээс тооцсон. "
        + 'Сэдвийн ангиллыг оруулаагүй: "гэнэт шуугисан" гэсэн ангилал өөрөө ирээдүйг хэлчихдэг (leakage).'],
      ["Хуваах", `${p.purge_days} өдөр`, "хил дээр хассан", "Сургах, сонгох, шалгах гурван үе",
        `Өгөгдлийг цаг хугацаагаар нь гурав хуваасан: сургах (train, ${ym(p.train_end)} хүртэл), сонгох (validation, ${ym(p.valid_end)} хүртэл), `
        + `эцэст нь шалгах (test, ${ym(p.end)} хүртэл). `
        + `Model ${p.horizons} өдрийн дараахыг таамагладаг тул хэсэг бүрийн сүүлийн ${p.purge_days} өдрийг хассан (purge). `
        + 'Эс бөгөөс сургалтын сүүлийн мөрийн "зөв хариулт" дараагийн хэсэгт орчихно.'],
      ["Сургах", num(p.trials), "оролдлого (trial)", `${p.n_algos} алгоритм × ${p.horizons} өдөр × ${p.n_trials} оролдлого`,
        `${algos} гурвыг ${days} өдрийн дараах таамаг (horizon) тус бүрт тусад нь сургасан. `
        + "Тохиргоог нь Optuna автоматаар хайсан: оролдлого (trial) бүрт өөр тохиргоо туршиж, муу нь эрт зогсоно. "
        + "Гурвуулаа ижил өгөгдөл, ижил feature, ижил тооны оролдлого авсан."],
      ["Сонгох", p.algo_name, "сонгосон", "Validation дээр хамгийн бага алдсан",
        `Гурван алгоритмыг сургалтад ороогүй ${validMonths} сарын өгөгдөл (validation) дээр шалгаж, дундаж алдаа (MAE) хамгийн багатайг нь сонгосон. `
        + `${After} харьцуулалтаас хассан: тэднийг ирээдүйг нь мэдэж сонгосон тул шударга шалгуур биш. `
        + "Эцсийн шалгалтын өгөгдлийг (test) сонголтод огт хэрэглээгүй. "
        + `Гурав бараг ижил гарсан, доорх "Яагаад ${p.algo_name}?" хэсгийг үзнэ үү.`],
      ["Шалгах", `${skill}%`, "бага алдаа", `${p.horizons} өдрийн дараа, ${naive}-аас`,
        `Test өгөгдлийг (${testSpan}, model огт хараагүй ${testMonths} сар) зөвхөн нэг удаа үнэлсэн, дараа нь юу ч тааруулаагүй. `
        + `Гол дүгнэлтийг ${chosen} дээр хийсэн: гэнэт шуугисан сэдвүүдийг ирээдүйг нь мэдэж сонгосон тул тэд шударга шалгуур биш. `
        + `"${skill}% бага алдаа" = энгийн аргаас хэдэн хувь бага алдсан (skill score).`],
      ["Вэб", md(p.asof), "хүртэлх өгөгдөл", "Өдөр бүр шинэ өгөгдлөөр таамаглана",
        `Сервер өдөр бүр Wikimedia-аас шинэ өдрийн уншилтыг татаж, сургалттай ижил кодоор цэвэрлээд ${p.algo_name} model-оор ирэх ${p.horizons} өдрийг таамаглана. `
        + "Model-ийг сайт дээр дахин сургадаггүй."],
    ].map(([title, value, unit, line, more]) => ({ title, value, unit, line, more }));
    return {
      errHint: `Дунджаар хэдэн хувиар зөрдөг вэ (${testSpan}, model огт хараагүй ${testMonths} сарын test өгөгдөл, ${chosen}). Ойр = илүү зөв.`,
      overfitSub: "Overfit = сургалтын өгөгдлөө цээжлээд шинэ өгөгдөл дээр муу таамаглах. Хоёр шугам ойрхон бол цээжлээгүй.",
      overfitNote: `Validation (сургалтад ороогүй шалгах өгөгдөл) дээрх алдаа сургалтынхаас бага гарсан нь алдаа биш: тэр ${validMonths} сар илүү тайван байсан. `
        + `Харьцуулахад ${naive} энгийн арга ч мөн тэр үед бага алдсан: дунджаар ${maePct(p.naive_h3.train).toFixed(1)}% → ${maePct(p.naive_h3.valid).toFixed(1)}% зөрсөн `
        + `(лог MAE ${p.naive_h3.train.toFixed(3)} → ${p.naive_h3.valid.toFixed(3)}).`,
      steps,
      // "Шударга уралдаан": budget-ийн өмнө app.js "ижил өгөгдөл, ижил N feature"-ийг (тод тоотой) тавина
      fairBudget: `тохиргоог нь Optuna-аар ижил тооны оролдлогоор (trial, ${p.n_trials} × ${p.horizons}) хайсан.`,
      fairRule: `1–${p.horizons} өдрийн дундаж validation алдаагаар сонгосон, validation-оос ${after} хассан.`,
      algoChart: `Дундаж validation алдаа (1–${p.horizons} өдөр)`,
      algoChartLabel: "Гурван алгоритм ба энгийн аргын дундаж validation алдаа",
      tableTitle: "Алгоритм бүрийн алдаа (validation)",
      tableCaption: `Дунджаар хэдэн хувиар зөрдөг вэ. ${After} оруулаагүй. Сонгосон нь тод.`,
      strength: {
        lightgbm: "Хамгийн хурдан: модоо навч навчаар нь ургуулдаг тул том өгөгдөлд хэмнэлттэй.",
        xgboost: "Хамгийн олон жил туршигдсан: регуляризаци сайтай, үр дүн нь тогтвортой.",
        catboost: "Бага тохируулгаар ч цээжлэх (overfit) нь бага: тэгш хэмтэй мод (symmetric trees), ordered boosting.",
      },
      importanceSub: 'Feature = model-д өгдөг тоо (жишээ нь "өчигдрөөс хэр өссөн"). Урт = таамагт илүү нөлөөтэй (feature importance).',
    };
  };

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
    HOLIDAY_TITLE, holidayLabel, holidayNote,
    num, maePct, months, modelWords };
  if (typeof module !== "undefined" && module.exports) module.exports = Words;
  else root.Words = Words;
})(typeof window !== "undefined" ? window : globalThis);
