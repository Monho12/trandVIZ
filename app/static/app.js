// Шуугиан — энгийн hash router + хуудсууд
(function () {
  const C = window.Charts, W = window.Words;
  const main = document.getElementById("main");
  const CATS = {
    politics: ["🏛️", "Улс төр"], film_tv: ["🎬", "Кино, цуврал"], true_crime: ["🕯️", "True crime"],
    tech_ai: ["🤖", "AI, технологи"], sports: ["⚽", "Спорт"], music: ["🎵", "Хөгжим"],
    games_anime: ["🎮", "Тоглоом, anime"], celebs: ["💅", "Алдартнууд"], society: ["👥", "Нийгэм"],
    mongolia: ["🇲🇳", "Монгол"], "Бусад": ["🌐", "Бусад"],   // вирал сэдвийн ангилал (ADR 0005)
  };
  const ORDER = Object.keys(CATS).filter((k) => k !== "Бусад");
  const cat = (k) => (CATS[k] || ["", k]).join(" ");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const href = (a) => "#/topic/" + encodeURIComponent(a);
  // ▲ = өнгөрсөн (ADR 0014). d: asof ба age_days-тэй хариу (meta_block)
  const surge = (r, d, short) => r >= 1.5
    ? `<span class="surge" title="${esc(W.surgeTip(r, d.asof))}">${esc(W.surgeText(r, d.asof, d.age_days, short))}</span>`
    : `<span class="surge calm">ердийн</span>`;
  const last = (t) => t.history[t.history.length - 1].v;
  const in3 = (t) => t.forecast[t.forecast.length - 1];
  // Нүүрний чип: таамгийн шошго (API-ийн label, сум нь дотроо), ▲ биш (#31)
  const chip = (t, d) => `<span class="fcl${t.fire ? " fire" : ""}">${esc(W.forecastLabel(t.label, d.asof, d.age_days))}</span>`;
  // Таамгийн хувь (ADR 0003/0004, 0014): backend-ийн pct(h3), сум, 🔥. Хувь = "анхаарал", тоо = "уншилт".
  const tipped = (text, tip) => `<span class="anh" title="${esc(tip)}">${esc(text)}</span>`;
  const pct = (t, d) => `${tipped("анхаарал", W.TIP.attention)} ${esc(W.forecastLabel(t.label, d.asof, d.age_days))}`;
  const iv = (t) => {
    const text = W.interval(t.interval_text), cut = text.indexOf(": ");   // tooltip нь "10 удаагийн 8-д" дээр
    if (!text) return "";
    return `<span class="iv">${cut < 0 ? tipped(text, W.TIP.interval) : tipped(text.slice(0, cut), W.TIP.interval) + esc(text.slice(cut))}</span>`;
  };

  let redraws = [], rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => redraws.forEach((f) => f()), 150); });
  const draw = (fn) => { redraws.push(fn); fn(); return fn; };

  const cache = {};
  const api = (p) => (cache[p] ||= fetch(p).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }));
  function meta(d) {
    document.getElementById("asof").textContent = `Өгөгдөл: ${C.longDate(d.asof)} хүртэл`;
    const s = document.getElementById("stale-note");
    s.hidden = !d.stale;
    if (d.stale) s.textContent = `Өгөгдөл ${d.age_days} өдрийн өмнөх (${C.md(d.asof)} хүртэл): Wikimedia-аас шинэчилж амжаагүй байна.`;
  }

  // Сэдвийн дэлгэрэнгүй хэсэг (нүүр болон сэдвийн хуудсанд хоёуланд)
  function focusHTML(t, d, { titleTag = "h2", link = true } = {}) {
    const normal = t.views / Math.max(t.ratio, 0.01);
    const title = link ? `<a href="${href(t.article)}">${esc(t.title)}</a>` : esc(t.title);
    return `
      <div class="focus-head">
        <${titleTag} class="focus-title">${title}</${titleTag}>
        <span class="focus-cat">${cat(t.category)}</span>
      </div>
      <dl class="tiles">
        <div class="tile t-blue"><dt>${W.dayTile(d.asof, d.age_days)}</dt><dd>${C.fmt(t.views)}<small>уншилт</small></dd></div>
        <div class="tile"><dt>${tipped("Ердийн өдөр", W.TIP.normal)}</dt><dd>${C.fmt(normal)}<small>${t.ratio >= 1.5 ? `×${t.ratio}` : ""}</small></dd></div>
        <div class="tile t-forecast"><dt>${C.md(in3(t).d)}-нд (таамаг)</dt><dd>≈ ${C.fmt(in3(t).y)}<small>уншилт</small><small class="sub">${pct(t, d)}</small><small class="iv">${iv(t)}</small></dd></div>
      </dl>
      <p class="chart-h">Өдөр бүрийн уншилт</p>
      <div class="chart" id="chart"></div>
      <ul class="key">
        <li><i class="k-blue"></i>Бодит</li>
        <li><i class="k-forecast"></i>Таамаг</li>
        <li><i class="k-norm"></i>Ердийн өдөр</li>
        <li><i class="k-range"></i>Таамгийн хүрээ</li>
      </ul>`;
  }
  const drawFocus = (t, d) => () => C.columns(document.getElementById("chart"), { ...t, axis: true, normal: t.views / Math.max(t.ratio, 0.01),
    day: W.day(d.asof, d.age_days),
    label: `${t.title}: өдөр бүрийн уншилт ба ирэх 3 өдрийн таамаг` });

  // ═════════ Нүүр ═════════
  async function home() {
    const [tr, cs, mp] = await Promise.all([api("/api/trending"), api("/api/categories"), api("/api/map")]);
    meta(tr);
    const top = tr.items.slice(0, tr.top_n);
    const count = (k) => tr.items.filter((t) => t.category === k).length;   // ангиллын бодит сэдвийн тоо
    const chans = ORDER.map((k) => cs.categories.find((c) => c.key === k)).filter(Boolean);
    const EMO = Object.fromEntries(Object.entries(CATS).map(([k, v]) => [k, v[0]]));
    main.innerHTML = `
      <h1 class="page-h">${W.homeTitle(tr.asof, tr.age_days)}</h1>
      <div class="map-key">
        <span><b>Том</b> = олон хүн уншсан</span>
        <span class="scale"><b>Өнгө</b> = ердийнхөөс
          <i style="background:#2a78d6"></i><em>бага</em>
          <i style="background:#eef1f5;outline:1px solid #d5dae3;outline-offset:-1px"></i><em>ердийн</em>
          <i style="background:#f4a3a9"></i><i style="background:#b5222e"></i><em>их шуугиж байна</em></span>
        <span>${esc(W.mapScope(tr.items.length, mp.items.length))}</span>
      </div>
      <div class="tmap" id="tmap"></div>
      <h2 class="sub-h">Ирэх 3 өдөрт юу өсөх вэ?</h2>
      <p class="lead">${esc(W.trendLead(tr.dates, tr.fires, tr.T, tr.top_n))} ${tipped(W.LOW_VIEWS, W.TIP.lowViews)}</p>
      <ul class="picker" aria-label="Сэдэв сонгох">${top.map((t, i) => `
        <li><button class="pick" data-i="${i}" aria-pressed="${i === 0}">${esc(t.title)} ${chip(t, tr)}</button></li>`).join("")}
      </ul>
      <section class="focus" id="focus" aria-live="polite"></section>
      <section class="sec" aria-labelledby="cat-h">
        <h2 id="cat-h">Ангилал бүрт юу уншигдав?</h2>
        <p class="lead">${esc(W.catLead(chans.length, chans.reduce((n, c) => n + count(c.key), 0) / chans.length, Math.max(...chans.map((c) => c.topics.length)),
          cs.asof, cs.age_days, W.catReason()))}</p>
        <div class="cats">${chans.map((c) => `
          <div class="cat">
            <h3>${cat(c.key)}</h3>
            <ul>${c.topics.map((t) => `<li><a href="${href(t.article)}">${esc(t.title)}</a><span class="sp" data-a="${esc(t.article)}" data-k="${c.key}"></span>${surge(t.ratio, cs, true)}</li>`).join("")}</ul>
            <a class="more" href="#/list/${encodeURIComponent(c.key)}">${esc(W.seeAll(count(c.key)))}</a>
          </div>`).join("")}
        </div>
      </section>`;

    draw(() => C.treemap(document.getElementById("tmap"), mp.items, { emoji: EMO, label: `Уншилтын газрын зураг, ${C.md(mp.asof)}` }));
    const byKey = Object.fromEntries(cs.categories.map((c) => [c.key, c.topics]));
    draw(() => main.querySelectorAll(".sp").forEach((b) => {
      const t = byKey[b.dataset.k].find((x) => x.article === b.dataset.a);
      if (t) C.spark(b, t.history);
    }));
    const btns = [...main.querySelectorAll(".pick")];
    let fn = null;
    function select(i) {
      btns.forEach((b, j) => b.setAttribute("aria-pressed", j === i));
      const t = top[i];
      document.getElementById("focus").innerHTML = focusHTML(t, tr);
      redraws = redraws.filter((f) => f !== fn);
      fn = draw(drawFocus(t, tr));
    }
    btns.forEach((b) => b.addEventListener("click", () => select(+b.dataset.i)));
    select(0);
  }

  // ═════════ Бүх сэдэв ═════════
  async function list() {
    const tr = await api("/api/trending");
    meta(tr);
    main.innerHTML = `
      <h1 class="page-h">Бүх сэдэв</h1>
      <p class="lead">Цэнхэр = бодит уншилт, улаан = таамаг</p>
      <ol class="rows">${tr.items.map((t, i) => `
        <li class="row">
          <span class="rk">${i + 1}</span>
          <div>
            <h3><a href="${href(t.article)}">${esc(t.title)}</a></h3>
            <p class="meta">${surge(t.ratio, tr)}<span><b>${C.fmt(t.views)}</b> уншилт</span><span>${esc(t.dates)}: ${pct(t, tr)} ${iv(t)}</span><span>${cat(t.category)}</span></p>
          </div>
          <div class="mini" data-i="${i}"></div>
        </li>`).join("")}
      </ol>`;
    draw(() => main.querySelectorAll(".mini").forEach((b) => {
      const t = tr.items[+b.dataset.i];
      C.columns(b, { history: t.history, forecast: t.forecast, label: `${t.title}: 30 хоног ба таамаг` });
    }));
  }

  // ═════════ Нэг сэдэв ═════════
  async function topic(article) {
    const t = await api("/api/topic/" + encodeURIComponent(article));
    meta(t);
    main.innerHTML = `
      <a class="back" href="#/">← Нүүр рүү буцах</a>
      <section class="focus topic" style="margin-top:14px">${focusHTML(t, t, { titleTag: "h1", link: false })}
        <table class="fc">
          <caption>Ирэх 3 өдрийн таамагласан уншилт. ${W.TIP.table}</caption>
          <thead><tr><th>Өдөр</th><th>Доод</th><th>Таамаг</th><th>Дээд</th></tr></thead>
          <tbody>${t.forecast.map((f) => `<tr><td>${C.longDate(f.d)}</td><td>${C.fmt(f.lo)}</td><td class="y">${C.fmt(f.y)}</td><td>${C.fmt(f.hi)}</td></tr>`).join("")}</tbody>
        </table>
      </section>`;
    draw(drawFocus(t, t));
  }

  // ═════════ Загвар ═════════
  // Feature-ийн энгийн монгол нэр (meta.json-ийн нэрээс)
  const FEAT = { ratio_7: "7 хоногийн дунджаас хэр зөрж байна", roll_std_3: "Сүүлийн 3 өдрийн савлагаа",
    growth_1: "Өмнөх өдрөөс хэр өссөн", vs_level: "Ердийн түвшнээсээ хэр дээр", dow: "Гарагийн өдөр",
    growth_3: "3 өдрийн өсөлт", roll_std_7: "7 хоногийн савлагаа", roll_std_14: "14 хоногийн савлагаа",
    roll_std_28: "28 хоногийн савлагаа", roll_mean_7: "7 хоногийн дундаж", roll_max_28: "28 хоногийн оргил",
    from_max_28: "28 хоногийн оргилоос хэр доор", days_since_peak: "Оргилоос хойш хэдэн хоног",
    doy_sin: "Жилийн аль үе", doy_cos: "Жилийн аль үе", level_365: "Жилийн ердийн түвшин", month: "Сар", is_weekend: "Амралтын өдөр эсэх" };
  const STRENGTH = {
    lightgbm: "Хамгийн хурдан: модоо навч навчаар нь ургуулдаг тул том өгөгдөлд хэмнэлттэй.",
    xgboost: "Хамгийн олон жил туршигдсан: регуляризаци сайтай, үр дүн нь тогтвортой.",
    catboost: "Тэгш хэмтэй мод ба ordered boosting: бага тохиргоотой ч overfit бага.",
  };
  const num = (v) => Number(v).toLocaleString("en-US").replace(/,/g, " ");
  const dot = (s) => s.replaceAll("-", ".");

  function pipelineSteps(p, m) {
    const ym = (s) => dot(s.slice(0, 7));
    return [
      ["Цуглуулах", num(p.topics), "сэдэв", `Wikipedia-ийн өдөр тутмын уншилт, ${p.years} жил`,
        `Wikimedia Pageviews API-аас англи Wikipedia-ийн ${dot(p.start)}–${dot(p.end)} хоорондох өдөр тутмын уншилтыг татсан, зөвхөн хүний (bot биш).
         Нэр нь солигдсон нийтлэлийн хуучин нэрийн уншилтыг нэгтгэсэн. Анхаарлыг тооцохын тулд Wikipedia-ийн нийт уншилтыг ч татсан.`],
      ["Цэвэрлэх", num(Math.round(p.clean_rows / 1000)), "мянган мөр", "Огцом bot үсрэлт, хоосон эхлэлийг зассан",
        `Ганц өдрийн тусгаарлагдсан огцом үсрэлтийг хязгаарласан. Сэдэв идэвхтэй болохоос өмнөх хоосон өдрүүдийг зөвхөн өнгөрсөн өгөгдлөөр шийдэж хассан.
         Эцэст нь уншилтыг тухайн өдрийн нийт уншилтад хувааж "анхаарал" болгосон.`],
      ["Feature", num(p.n_features), "feature", "Өсөлт, савлагаа, гараг, улирал",
        `Feature бүрийг зөвхөн өнгөрсөн өдрүүдээс тооцсон. Хоорондоо хэт төстэй feature-ийг хасаж ${p.n_features}-ийг үлдээсэн.
         Сэдвийн ангиллыг ("вирал" гэх мэт) ирээдүйг илтгэдэг тул model-д оруулаагүй.`],
      ["Хуваах", `${p.purge_days} өдөр`, "хил дээр хассан", `Train ${ym(p.train_end)} хүртэл, valid ${ym(p.valid_end)}, test ${ym(p.end)}`,
        `Цаг хугацаагаар нь хуваасан, санамсаргүй холиогүй. Хил бүр дээр ${p.purge_days} өдрийг хассан (purge): эс бөгөөс ${p.purge_days} өдрийн дараах хариулт нь дараагийн хэсгээс ирж, мэдээлэл нэвчинэ.
         Сургалтад ${dot(p.train_from)}-аас хойшх ${num(p.train_rows)} мөр орсон.`],
      ["Сургах", num(p.trials), "Optuna trial", `${p.n_algos} алгоритм × ${p.horizons} horizon × ${p.n_trials}`,
        `LightGBM, XGBoost, CatBoost-ыг horizon тус бүрт тусад нь сургасан. Optuna параметрийг хайж, муу trial-ыг эрт зогсоосон.
         Гурвуулаа ижил өгөгдөл, ижил feature, ижил тооны trial авсан.`],
      ["Сонгох", p.algo_name, "сонгосон", "Дундаж valid алдаа хамгийн бага",
        `1–${p.horizons} өдрийн дундаж valid MAE-ээр сонгосон. Valid-аас шинэ вирал (в) сэдвүүдийг хассан, test-ийг огт ашиглаагүй.
         Гурав бараг ижил гарсан, доорх "Яагаад ${esc(p.algo_name)}?" хэсгийг үзнэ үү.`],
      ["Шалгах", `${Math.round(p.skill_h3)}%`, "бага алдаа", `${p.horizons} өдрийн дараа, "${esc(m.names.naive)}"-аас`,
        `Test-ийг (${dot(p.test_start)}–${dot(p.end)}) зөвхөн нэг удаа үнэлсэн, дахин тааруулаагүй.
         Гол дүгнэлтийг сонгосон сэдвүүд (а) дээр хийсэн. Дээрх "Таамаг хэр зөрдөг вэ?" хэсэг эндээс.`],
      ["Вэб", C.md(p.asof), "хүртэлх өгөгдөл", "Өдөр бүр шинэ өгөгдлөөр таамаглана",
        `Сервер өдөр бүр Wikimedia-аас шинэ өдрийг татаж, сургалттай ижил кодоор цэвэрлэж feature тооцоод ${esc(p.algo_name)} model-оор ирэх ${p.horizons} өдрийг таамаглана.
         Model-ийг сайт дээр дахин сургадаггүй.`],
    ];
  }

  async function model() {
    const m = await api("/api/model");
    meta(m);
    const p = m.pipeline, v = m.valid, N = m.names;
    const mdl = esc(N.model), nv = esc(N.naive);
    const h3 = m.metrics.find((r) => r.h === 3), e = Math.round(h3[m.winner]);
    const rows = m.metrics.map((r) => ({ name: `${r.h} өдрийн дараа`, model: r[m.winner], naive: r.naive, gain: m.skill["h" + r.h].point }));
    const others = v.algos.filter((a) => a !== m.winner), order = [m.winner, ...others];
    const spread = Math.max(...v.rows.map((r) => Math.max(...v.algos.map((a) => r[a])) - Math.min(...v.algos.map((a) => r[a]))));
    const vsNaive = Math.min(...v.rows.map((r) => r.naive - r[m.winner]));
    const steps = pipelineSteps(p, m);
    const grp = m.group;
    main.innerHTML = `
      <h1 class="page-h">Загвар хэр сайн таамагладаг вэ?</h1>
      <p class="lead">Энгийн аргаас илүү зөв үү?</p>
      <p class="chart-sub">Сайтын ард ажиллаж буй model: <b>${esc(m.live.algo_name)}</b>, сургасан ${C.md(m.live.trained_at.slice(0, 10))},
        өгөгдөл ${C.md(m.live.data_asof)} хүртэл, таамаг ${esc(m.dates)}</p>
      <div class="mgrid">
        <div class="mcard">
          <h3>Таамаг хэр зөрдөг вэ?</h3>
          <p class="big">3 өдрийн дараах таамаг "${nv}" аргаас <b>${Math.round(m.skill.h3.point)}%</b> бага алддаг.</p>
          <p class="chart-sub">100 гэж таамагласан бол бодит нь ихэвчлэн ~${100 - e}–${100 + e} орчим.</p>
          <ul class="key">
            <li><i class="k-dot"></i>${mdl}</li>
            <li><i class="k-dot k-dot-gray"></i>${nv}</li>
          </ul>
          <div class="mchart db" id="m-err"></div>
          <p class="note">${nv}: 3 өдрийн дараа ч анхаарал өнөөдрийнхтэй адилхан байна гэж таах хамгийн энгийн арга. Model үүнээс бага алдах ёстой.</p>
          <p class="hint">Дунджаар хэдэн хувиар зөрдөг вэ (test ${dot(p.test_start)}–${dot(p.end)}, сонгосон ${m.pipeline.topics_main} сэдэв (${grp})). Ойр = илүү зөв.</p>
        </div>
        <div class="mcard">
          <h3>Overfit болсон уу? <span class="h-sub">(${m.curve_h} өдрийн дараах model)</span></h3>
          <p class="chart-sub">Хоёр шугам ойрхон = сайн</p>
          <div class="mchart" id="m-curve"></div>
          <p class="note">Validation-ий алдаа ихэнхдээ сургалтынхаас бага байгаа нь leakage биш: validation үе илүү тайван байсан.
            "${nv}"-ийн алдаа ч сургалтын үед ${p.naive_h3.train.toFixed(3)}, validation үед ${p.naive_h3.valid.toFixed(3)} (лог MAE).</p>
        </div>
      </div>

      <section class="sec" aria-labelledby="pl-h">
        <h2 id="pl-h">Яаж хийсэн бэ?</h2>
        <p class="lead">Карт дээр дарж дэлгэрэнгүйг үзнэ үү.</p>
        <ol class="pl">${steps.map(([t, n, u, line, more], i) => `
          <li class="pl-step">
            <button class="pl-card" aria-expanded="false" aria-controls="pl-more-${i}" data-i="${i}">
              <span class="pl-n">${i + 1}</span>
              <span class="pl-t">${t}</span>
              <span class="pl-v">${esc(n)}</span><span class="pl-u">${esc(u)}</span>
              <span class="pl-l">${line}</span>
            </button>
            <p class="pl-more" id="pl-more-${i}" hidden>${more}</p>
          </li>`).join("")}
        </ol>
        <p class="pl-panel" id="pl-panel" aria-live="polite" hidden></p>
      </section>

      <section class="sec" aria-labelledby="why-h">
        <h2 id="why-h">Яагаад ${esc(p.algo_name)}?</h2>
        <p class="lead">Алгоритмаас илүү feature чухал байсан.</p>
        <div class="mgrid">
          <div class="mcard">
            <h3>Шударга уралдаан</h3>
            <ul class="why">
              <li>Гурвуулаа ижил өгөгдөл, ижил <b>${p.n_features}</b> feature, ижил Optuna төсөв (${p.n_trials} trial × ${p.horizons} horizon).</li>
              <li>1–${p.horizons} өдрийн дундаж valid алдаагаар сонгосон, valid-аас шинэ вирал (в) сэдвийг хассан. <b>Test-ийг ашиглаагүй.</b></li>
              <li>Гурав бараг ижил: хоорондоо ${spread.toFixed(2)} нэгжээс бага зөрдөг, харин "${nv}"-аас ${vsNaive.toFixed(1)}+ нэгж бага.</li>
            </ul>
            <p class="chart-h">Дундаж valid алдаа (1–${p.horizons} өдөр)</p>
            <div class="mchart" id="m-algo" style="height:150px"></div>
          </div>
          <div class="mcard">
            <h3>Алгоритм бүрийн алдаа, valid</h3>
            <table class="fc vt">
              <caption>Дунджаар хэдэн хувиар зөрдөг вэ, (в)-гүй valid. Сонгосон нь тод.</caption>
              <thead><tr><th>Арга</th>${v.rows.map((r) => `<th>${r.h} өдөр</th>`).join("")}<th>Дундаж</th></tr></thead>
              <tbody>${order.map((a) => `<tr class="${a === m.winner ? "y" : ""}"><td>${esc(N[a])}</td>${v.rows.map((r) => `<td>${r[a].toFixed(2)}%</td>`).join("")}<td>${v.mean[a].toFixed(2)}%</td></tr>`).join("")}
                <tr class="nv"><td>${nv}</td>${v.rows.map((r) => `<td>${r.naive.toFixed(2)}%</td>`).join("")}<td>${v.mean.naive.toFixed(2)}%</td></tr></tbody>
            </table>
            <p class="hint">Сонголтын дүрэм (дундаж лог MAE): ${order.map((a) => `${esc(N[a])} ${v.mean_log[a].toFixed(5)}`).join(" · ")}</p>
            <ul class="why str">${order.map((a) => `<li><b>${esc(N[a])}</b> ${STRENGTH[a] || ""}</li>`).join("")}</ul>
          </div>
          <div class="mcard" style="grid-column:1/-1">
            <h3>Model юуг хамгийн их хардаг вэ? <span class="h-sub">(эхний 5)</span></h3>
            <p class="chart-sub">Урт = илүү чухал (${esc(p.algo_name)}-ийн feature importance)</p>
            <div class="mchart" id="m-imp" style="height:220px"></div>
          </div>
        </div>
      </section>`;

    draw(() => C.dumbbell(document.getElementById("m-err"), rows, { names: N, label: `${N.model} ба ${N.naive}: алдааг хувиар, 1–3 өдрийн дараа` }));
    draw(() => C.curve(document.getElementById("m-curve"), m.curve, m.best_iter, `Сургалт ба validation алдааны муруй, ${m.curve_h} өдрийн дараах model`));
    draw(() => C.hbarsV(document.getElementById("m-algo"), [...order, "naive"].map((a) => ({
      name: N[a], v: v.mean[a], cls: a === m.winner ? "b-blue" : a === "naive" ? "b-naive" : "b-gray",
      tip: `<b>${esc(N[a])}</b>Дунджаар ${v.mean[a].toFixed(2)}% зөрдөг` })),
      { fmt: (x) => x.toFixed(2) + "%", hiN: 1, lw: 150, label: "Гурван алгоритм ба энгийн аргын дундаж valid алдаа" }));
    draw(() => C.hbarsV(document.getElementById("m-imp"), m.importance_share.slice(0, 5).map((r) => ({
      name: FEAT[r.f] || r.f, v: r.share, cls: "b-blue", tip: `<b>${esc(FEAT[r.f] || r.f)}</b>${r.share}% <span>(${esc(r.f)})</span>` })),
      { fmt: (x) => x.toFixed(1) + "%", hiN: 0, lw: 260, stackBelow: 560, label: "Feature importance, эхний 5" }));

    // Алхмын карт: утсанд картын доор, том дэлгэцэнд мөрийн доорх нэг талбайд дэлгэрнэ
    const cards = [...main.querySelectorAll(".pl-card")], panel = document.getElementById("pl-panel");
    cards.forEach((b) => b.addEventListener("click", () => {
      const open = b.getAttribute("aria-expanded") !== "true";
      cards.forEach((c) => { c.setAttribute("aria-expanded", "false"); c.nextElementSibling.hidden = true; });
      if (open) { b.setAttribute("aria-expanded", "true"); b.nextElementSibling.hidden = false; }
      panel.hidden = !open;
      panel.innerHTML = open ? `<b>${steps[+b.dataset.i][0]}.</b> ${steps[+b.dataset.i][4]}` : "";
    }));
  }

  // ═════════ Сонирхолтой ═════════
  async function facts() {
    const d = await api("/api/insights");
    document.getElementById("stale-note").hidden = true;
    const dec3 = Math.round(d.decay[3]);
    const topCat = d.categories[0];
    const pick = [["tech_ai", "Ажлын өдөр"], ["sports", "Ням гараг"], ["true_crime", "Амралтын өдөр"], ["film_tv", "Ням гараг"]];
    const mn = d.mongolia[0];
    main.innerHTML = `
      <h1 class="page-h">Сонирхолтой</h1>
      <p class="lead">Wikipedia-ийн 5 жилийн өгөгдлөөс</p>
      <div class="fgrid">
        <section class="fcard">
          <h3>Шуугиан хэр хурдан мартагддаг вэ?</h3>
          <p class="big"><b>${dec3}%</b> нь л 3 хоногийн дараа үлддэг</p>
          <div class="fchart" id="f-decay"></div>
        </section>
        <section class="fcard">
          <h3>Дэлхий юуг хамгийн их уншдаг вэ?</h3>
          <p class="big"><b>${CATS[topCat.key][1]}</b> сүүлийн 30 хоногт</p>
          <div class="fchart" id="f-cats" style="height:250px"></div>
        </section>
        <section class="fcard wide">
          <h3>Аль гарагт юу уншдаг вэ?</h3>
          <p class="big">Ажлын өдөр <b>AI</b>, амралтын өдөр <b>спорт, true crime</b></p>
          <div class="minis">${pick.map(([k, when]) => `
            <div><p class="mini-h">${cat(k)}</p><div class="fchart mini" data-k="${k}"></div><p class="mini-s">${when}</p></div>`).join("")}
          </div>
        </section>
        <section class="fcard">
          <h3>Баяр жил бүр давтагддаг</h3>
          <p class="big"><b>Хамгийн таамаглахад амар</b> сэдэв</p>
          <div class="fchart" id="f-hol"></div>
          <ul class="key"><li><i style="background:#2a78d6"></i>Зул сар</li><li><i style="background:#e63946"></i>Halloween</li><li><i style="background:#1D3557"></i>Валентин</li></ul>
        </section>
        <section class="fcard">
          <h3>Дэлхий Монголын юуг уншдаг вэ?</h3>
          <p class="big"><b>${Math.round(mn.share)}%</b> нь ${mn.title === "Genghis Khan" ? "Чингис хаан" : esc(mn.title)}</p>
          <div class="fchart" id="f-mn" style="height:220px"></div>
        </section>
      </div>`;
    const DAYS = ["Да", "Мя", "Лх", "Пү", "Ба", "Бя", "Ня"];
    draw(() => C.bars(document.getElementById("f-decay"), d.decay, {
      labels: d.decay.map((_, i) => (i === 0 ? "оргил" : [3, 7, 14].includes(i) ? `${i} хоног` : "")),
      hi: [0, 3], valLabels: { 0: "100%", 3: `${dec3}%`, 7: `${Math.round(d.decay[7])}%` }, label: "Оргилын дараах өдрүүдэд уншилт хэдэн хувь үлддэг вэ" }));
    draw(() => C.hbarsV(document.getElementById("f-cats"), d.categories.map((c) => ({ name: catOnly(c.key), v: c.views })),
      { fmt: C.fmt, hiN: 1, label: "Ангилал бүрийн сүүлийн 30 хоногийн уншилт" }));
    draw(() => main.querySelectorAll(".mini").forEach((b) => {
      const v = d.weekday[b.dataset.k], mx = v.indexOf(Math.max(...v));
      C.bars(b, v, { labels: DAYS, hi: [mx], base: 100, minY: 70, label: `${catOnly(b.dataset.k)}: гарагаар` });
    }));
    draw(() => C.lines(document.getElementById("f-hol"), d.holidays.months, d.holidays.series,
      { label: "Баярын нийтлэлүүдийн сар бүрийн уншилт" }));
    draw(() => C.hbarsV(document.getElementById("f-mn"), d.mongolia.map((r) => ({ name: MN[r.title] || r.title, v: r.share })),
      { fmt: (v) => Math.round(v) + "%", hiN: 1, label: "Монголын сэдвүүдийн эзлэх хувь" }));
  }
  const catOnly = (k) => (CATS[k] || ["", k])[1];
  const MN = { "Genghis Khan": "Чингис хаан", Mongolia: "Монгол Улс", "Mongol Empire": "Монголын эзэнт гүрэн",
    "Kublai Khan": "Хубилай хаан", "Golden Horde": "Алтан Орд", Ulaanbaatar: "Улаанбаатар", Mongols: "Монголчууд", "Ögedei Khan": "Өгөдэй хаан" };

  // ═════════ Router ═════════
  async function route() {
    redraws = [];
    document.getElementById("tip").hidden = true;
    const [page, arg] = location.hash.replace(/^#\/?/, "").split("/");
    const name = ["list", "model", "topic", "facts"].includes(page) ? page : "home";
    document.querySelectorAll(".nav a").forEach((a) =>
      a.dataset.route === name ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
    main.innerHTML = `<p class="state">Ачаалж байна…</p>`;
    try {
      if (name === "list") await list();
      else if (name === "facts") await facts();
      else if (name === "model") await model();
      else if (name === "topic") await topic(decodeURIComponent(arg || ""));
      else await home();
    } catch (e) {
      main.innerHTML = `<p class="state">Өгөгдөл ачаалж чадсангүй (${esc(e.message)}). Хуудсыг дахин ачаалж үзнэ үү.</p>`;
    }
    if (name !== "home") main.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", route);
  route();
})();
