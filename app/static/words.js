// Сайтын үг ба шошго (ADR 0014): тоо = "уншилт", таамгийн хувь = "анхаарал"; ▲ = өнгөрсөн, ↗/🔥 = таамаг.
// "Өчигдөр" гэдэг үг зөвхөн эндээс, asof = өчигдөр (age_days = 1) үед л гарна; бусад үед огноо.
// asof: "YYYY-MM-DD", age: /api/*-ийн age_days (серверийн өнөөдөр, Улаанбаатарын цагаар − asof).
(function (root) {
  // ── Огноо (ADR 0018). Сайтын бүх огноо эндээс гарна (charts.js, app.js өөрөө огноо задлахгүй, test_words шалгана). ──
  // iso: "YYYY-MM-DD" (эсвэл "YYYY-MM-DDTHH:MM..."-ийн эхний 10 тэмдэгт).
  const ymd = (iso) => iso.slice(0, 10).split("-").map(Number);
  const pad = (n) => String(n).padStart(2, "0");
  // Карт, графикийн тэнхлэг, богино шошго (▲, чип), хугацаа: "11.09" (YYYY.MM.DD-ийн сар.өдөр, тэгээр нөхсөн). src/serve.py: md()-тэй ижил.
  const md = (iso) => { const [, m, d] = ymd(iso); return `${pad(m)}.${pad(d)}`; };
  // Өгүүлбэр, tooltip, гарчиг: "11-р сарын 9". ref (сайтын asof) өгвөл жил нь өөр үед "2025 оны 11-р сарын 9".
  const longDate = (iso, ref) => {
    const [y, m, d] = ymd(iso);
    return `${ref && y !== ymd(ref)[0] ? `${y} оны ` : ""}${m}-р сарын ${d}`;
  };
  // Олон жилийн хүрээ (жил заавал): "2026.10.08–2026.11.06"; сар: "2026.05"
  const fullDate = (iso) => { const [y, m, d] = ymd(iso); return `${y}.${pad(m)}.${pad(d)}`; };
  const span = (r) => `${fullDate(r.from)}–${fullDate(r.to)}`;
  const ym = (iso) => fullDate(iso).slice(0, 7);

  const isYesterday = (age) => age === 1;
  const day = (asof, age) => (isYesterday(age) ? "өчигдөр" : md(asof));                      // шошго, график
  const dayTile = (asof, age) => (isYesterday(age) ? "Өчигдөр" : md(asof));

  // t: /api/*-ийн сэдэв (ratio, views_ratio, typical_pct, similar_days). Түүхий уншилтын ×N хаалтанд (CONTEXT.md).
  const surgeTip = (t, asof) => [
    `${longDate(asof)}-нд анхаарал ердийн өдрөөс ${t.ratio} дахин их${t.views_ratio == null ? "" : ` (уншилт ×${t.views_ratio})`}.`,
    `Энэ сэдэв ихэвчлэн ±${Math.round(t.typical_pct * 100)}%-иар л хэлбэлздэг.`,
    `Сүүлийн 2 сард ийм өдөр ${t.similar_days ? `${t.similar_days} удаа гарсан` : "нэг ч удаа гараагүй"}.`].join(" ");

  // API-ийн "80%: +10% … +85%" -> "10 удаагийн 8-д: +10% … +85%"
  const interval = (text) => (text ? text.replace(/^80%:\s*/, "10 удаагийн 8-д: ") : "");
  // API-ийн "— (өчигдөр уншилтгүй)" шошгыг хуучирсан өгөгдөлд огноотой болгоно
  const forecastLabel = (label, asof, age) => (isYesterday(age) ? label : label.replace("өчигдөр", `${md(asof)}-нд`));

  // ── "Сонирхолтой" хуудас (issue #33). Юуг харуулахыг app/data/make_insights.py сонгоно, энд зөвхөн үг. ──
  const DAYS = ["Да", "Мя", "Лх", "Пү", "Ба", "Бя", "Ня"];                                   // 0 = Даваа
  const DAYS_LONG = ["Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан", "Бямба", "Ням"];
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
      // h1-д "загвар" үг үлдээхгүй; "байсан": track record бол өнгөрсөн өгөгдөл (ADR 0022, 0027)
      title: "Таамаг өмнө нь хэр зөв байсан бэ?",
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

  // ── W7 (#52): нүүр, карт, "Бүх сэдэв" (ADR 0022, 0024, 0026, 0027). Огноо бүр энд. ──
  // Харьяалах тийн ялгал: "11.10-ны", "11.09-ний" (сүүлийн тэгээс өөр цифр 1, 4, 9 бол -ний: нэг, дөрөв, ес)
  const of = (iso) => { const d = ymd(iso)[2], k = d % 10 || Math.floor(d / 10); return `${md(iso)}-${[1, 4, 9].includes(k) && d % 10 ? "ний" : "ны"}`; };
  const signed = (p) => (p == null ? "—" : `${p > 0 ? "+" : p < 0 ? "−" : ""}${Math.round(Math.abs(p) * 100)}%`);
  const arrow = (p) => (p == null ? "" : p <= -0.1 ? "↘" : p >= 0.1 ? "↗" : "≈");   // ADR 0026: ↓-г ↘-д нэгтгэнэ
  const homeH1 = (asof, n) => (n === 0 ? `${md(asof)}-нд огцом өссөн сэдэв гараагүй`
    : `${md(asof)}-нд огцом өссөн ${n} сэдэв: ирэх 3 өдөрт үргэлжлэх үү, унтрах уу?`);
  // s: /api/trending-ийн anomalies ({n, continue, fade, all_fade}). Тоог app.js тодруулна: [өмнө, тоо, дараа] хэсгүүдээр
  const homeSum = (s) => (s.n === 0 ? [["Сэдвүүд ердийн түвшиндээ уншигдсан."]]
    : s.all_fade ? [["", s.n, " сэдвийн бүгд нь ирэх 3 өдөрт унтрах төлөвтэй."]]
      : [["", s.continue, " нь үргэлжлэх, "], ["", s.fade, " нь унтрах төлөвтэй."]]);
  const mapTitle = (asof) => `${md(asof)}-нд англи Wikipedia-д юу уншигдав?`;
  const MAP_KEY = { size: "Хэмжээ = уншилт", ratio: "ердийнхөөс ×1 … ×10+", dot: "огцом өссөн" };
  const cellLabel = (r, fmt) => `${r.title}: ${fmt(r.views)} уншилт, ердийнхөөс ×${r.ratio ?? 1}${r.anomaly ? ", огцом өссөн" : ""}`;
  const cellValue = (r, fmt) => `${fmt(r.views)} · ×${r.ratio ?? 1}`;
  const cellTip = (r, asof, fmt) => [r.title, `${fmt(r.views)} уншилт, ${longDate(asof)}`, `Ердийнхөөс ×${r.ratio ?? 1}${r.anomaly ? " · ● огцом өссөн" : ""}`];
  const VERDICT = { continue: "үргэлжлэх", fade: "унтрах" };
  const GROUP = { continue: "Үргэлжлэх төлөвтэй", fade: "Унтрах төлөвтэй" };
  const groupEmpty = (asof, v) => `${md(asof)}-нд "${VERDICT[v]}" төлөвтэй сэдэв алга.`;
  const seeAllN = (n) => `Бүгдийг харах (${n}) →`;
  const reviveTitle = (dates) => `${dates}-нд сэргэх төлөвтэй`;
  const REVIVE_LEAD = "Саяхан ердийн түвшнээсээ доош орсон, буцаж өсөх таамагтай сэдвүүд.";
  const REVIVE_EMPTY = "Энэ өдөр жагсаалтад сэдэв алга.";
  const cycleTitle = (n) => `Долоо хоногийн ердийн өсөлт (${n})`;
  const CYCLE_LEAD = "Эдгээр нь гарагийн ердийн хэв маягаар өсөх таамагтай: ховор дохио биш.";
  const CYCLE_WORD = "долоо хоног бүр ийм";
  const cycleTip = (c) => `Энэ гарагуудад ердийн долоо хоногт ${signed(c)} өөрчлөгддөг`;
  const markText = (r) => (r == null ? "огцом" : `×${r}`);
  const markTip = (t, asof) => `${longDate(asof)}-нд анхаарал ердийнхөөс ${t.ratio == null ? "огцом" : `×${t.ratio}`} өссөн`;
  const byDay = (iso) => `${md(iso)} гэхэд`;
  const MORE = "Ямар нөхцөлд?";
  const CODE_TEXT = {
    after_peak: "Сүүлийн 7 хоногт огцом өссөн өдөр байсан. Сүүлийн өдрийн уншилт тэр оргилоос доогуур байна.",
    growing: "Уншилт 7 хоногийн дунджаасаа дээгүүр, 3 өдрийн өмнөхөөсөө өндөр байна.",
    cycle: "Энэ гарагуудад уншилт ердийн долоо хоногт ийм өөрчлөгддөг.",
    rebound: "Огцом өсөөгүй. Уншилт 7 хоногийн дунджаасаа доош орсон байна.",
    total: "Тэр өдөр англи Wikipedia-ийн нийт уншилт ердийнхөөс огцом зөрсөн.",
    unclear: "Дээрх нөхцлүүдийн аль нь ч ажиглагдаагүй.",
  };
  const DISCLAIM = "Энэ нь таамгийн шалтгаан биш. Ийм үед өмнө нь юу болж байсныг харуулна.";
  const NEUTRAL = "Огцом уншилт сайн, муу гэсэн үг биш: нас баралт, дайн ч уншилтыг өсгөдөг.";
  // 3а-ийн track record (ADR 0020): Anomaly-д "≥ 10% буурсан", бусдад "долоо хоногийн ердийнхөөс ≥ 10% илүү өссөн"
  const tenOf = (rate) => Math.round(rate * 10);
  const codeWhat = (anomaly) => (anomaly ? "3 өдрийн дараа ≥ 10% буурсан" : "3 өдрийн дараа долоо хоногийн ердийнхөөс ≥ 10% илүү өссөн");
  const codeHit = (rate, anomaly) => [`10-аас ${tenOf(rate)}`, ` нь ${codeWhat(anomaly)}`];
  const codeBase = (rate) => `10-аас ${tenOf(rate)}: ердийн үед (бүх сэдэв)`;
  const codeFew = (minN) => `Ийм нөхцөлийн өмнөх тохиолдол хангалтгүй (n < ${minN}).`;
  const prov = (src, n) => `${src.source} · model ${src.model_version}${n == null ? "" : ` · n ${num(n)}`}`;
  const sparkLabel = (t, fmt) => {
    const h = t.history[t.history.length - 1], f = t.forecast[t.forecast.length - 1];
    return `${t.title}: сүүлийн 14 өдрийн уншилт, ${md(h.d)}-нд ${fmt(h.v)}. ${md(f.d)}-нд ≈ ${fmt(f.y)} гэж таамагласан, 80% магадлалтай ${fmt(f.lo)}–${fmt(f.hi)}.`;
  };
  // Мэдэгдэл: өгөгдөл дутуу (ADR 0022), хуучирсан, cold start, алдаа (ADR 0027)
  const incompleteNote = (day, asof) => `${of(day)} өгөгдөл Wikimedia-аас бүрэн ирээгүй. ${of(asof)} дүнг харуулж байна.`;
  const staleNote = (asof, age) => `Өгөгдөл ${age} өдрийн өмнөх (${longDate(asof)} хүртэл): Wikimedia-аас шинэчилж амжаагүй байна.`;
  const COLD = "Сервер унтаж байсан бол сэрэхэд хэсэг хугацаа шаардана. Хуудас өөрөө ачаалагдана.";
  const waited = (sec) => `${sec} секунд болж байна`;
  const ERROR = { what: "Өгөгдөл ирсэнгүй.", why: "Сервер түр ажиллахгүй байж магадгүй.", retry: "Дахин оролдох", retrying: "Оролдож байна…" };
  const LIST = {
    title: "Бүх сэдэв",
    lead: (asof, n, dates) => `${md(asof)}-ний ${n} сэдэв, ирэх 3 өдрийн (${dates}) таамагтай.`,
    filters: [["all", "Бүгд"], ["continue", "Үргэлжлэх"], ["fade", "Унтрах"]],
    sorts: [["views", "Уншилтаар"], ["up", "Өсөлтөөр"], ["down", "Бууралтаар"]],
    filterLabel: "Шүүлтүүр", sortLabel: "Эрэмбэ", more: (n) => `Дахиад харах (${n})`, none: (asof, v) => groupEmpty(asof, v),
    low: "цөөн уншилттай",
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

  const Words = { md, longDate, day, dayTile, surgeTip, interval, forecastLabel, TIP,
    DAYS, span, factsLead, decayNote, catsNote, mongoliaNote, catsHeadline, weekdayTitle, weekdayLabel, WEEKDAY_NOTE,
    HOLIDAY_TITLE, holidayLabel, holidayNote,
    num, maePct, months, modelWords,
    of, signed, arrow, homeH1, homeSum, mapTitle, MAP_KEY, cellLabel, cellValue, cellTip, VERDICT, GROUP, groupEmpty, seeAllN,
    reviveTitle, REVIVE_LEAD, REVIVE_EMPTY, cycleTitle, CYCLE_LEAD, CYCLE_WORD, cycleTip, markText, markTip, byDay, MORE, CODE_TEXT,
    DISCLAIM, NEUTRAL, tenOf, codeHit, codeBase, codeFew, prov, sparkLabel, incompleteNote, staleNote, COLD, waited, ERROR, LIST };
  if (typeof module !== "undefined" && module.exports) module.exports = Words;
  else root.Words = Words;
})(typeof window !== "undefined" ? window : globalThis);
