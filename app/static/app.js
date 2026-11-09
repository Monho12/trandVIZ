// Шуугиан — энгийн hash router + хуудсууд
(function () {
  const C = window.Charts;
  const main = document.getElementById("main");
  const CATS = {
    politics: ["🏛️", "Улс төр"], film_tv: ["🎬", "Кино, цуврал"], true_crime: ["🕯️", "True crime"],
    tech_ai: ["🤖", "AI, технологи"], sports: ["⚽", "Спорт"], music: ["🎵", "Хөгжим"],
    games_anime: ["🎮", "Тоглоом, anime"], celebs: ["💅", "Алдартнууд"], society: ["👥", "Нийгэм"],
    mongolia: ["🇲🇳", "Монгол"], viral: ["🔥", "Вирал"],
  };
  const ORDER = Object.keys(CATS).filter((k) => k !== "viral");
  const cat = (k) => (CATS[k] || ["", k]).join(" ");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const href = (a) => "#/topic/" + encodeURIComponent(a);
  const surge = (r, short) => r >= 1.5
    ? `<span class="surge" title="Хэвийн өдрөөс ${r} дахин их">×${r}${short ? "" : " хэвийнээс"}</span>`
    : `<span class="surge calm">хэвийн</span>`;
  const last = (t) => t.history[t.history.length - 1].v;
  const in3 = (t) => t.forecast[t.forecast.length - 1];
  const pct = (t) => {
    const p = Math.round((in3(t).y / Math.max(last(t), 1) - 1) * 100);
    return p < 0 ? `↓ ${-p}% буурна` : `↑ ${p}% өснө`;
  };

  let redraws = [], rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => redraws.forEach((f) => f()), 150); });
  const draw = (fn) => { redraws.push(fn); fn(); return fn; };

  const cache = {};
  const api = (p) => (cache[p] ||= fetch(p).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }));
  function meta(d) {
    document.getElementById("asof").textContent = `Өгөгдөл: ${C.longDate(d.asof)} хүртэл`;
    document.getElementById("mock-note").hidden = !d.mock;
  }

  // Сэдвийн дэлгэрэнгүй хэсэг (нүүр болон сэдвийн хуудсанд хоёуланд)
  function focusHTML(t, { titleTag = "h2", link = true, days = 30 } = {}) {
    const normal = t.views / Math.max(t.ratio, 0.01);
    const title = link ? `<a href="${href(t.article)}">${esc(t.title)}</a>` : esc(t.title);
    return `
      <div class="focus-head">
        <${titleTag} class="focus-title">${title}</${titleTag}>
        <span class="focus-cat">${cat(t.category)}</span>
      </div>
      <dl class="tiles">
        <div class="tile t-blue"><dt>Өчигдөр</dt><dd>${C.fmt(t.views)}</dd></div>
        <div class="tile"><dt>Ердийн өдөр</dt><dd>${C.fmt(normal)}<small>${t.ratio >= 1.5 ? `×${t.ratio}` : ""}</small></dd></div>
        <div class="tile t-orange"><dt>3 өдрийн дараа (таамаг)</dt><dd>≈ ${C.fmt(in3(t).y)}<small>${pct(t)}</small></dd></div>
      </dl>
      <p class="chart-h">Өдөр бүрийн уншилт</p>
      <div class="chart" id="chart"></div>
      <ul class="key">
        <li><i class="k-blue"></i>Бодит</li>
        <li><i class="k-orange"></i>Таамаг</li>
        <li><i class="k-norm"></i>Ердийн өдөр</li>
        <li><i class="k-range"></i>Таамгийн хүрээ</li>
      </ul>`;
  }
  const drawFocus = (t) => () => C.columns(document.getElementById("chart"), { ...t, axis: true, normal: t.views / Math.max(t.ratio, 0.01),
    label: `${t.title}: өдөр бүрийн уншилт ба ирэх 3 өдрийн таамаг` });

  // ═════════ Нүүр ═════════
  async function home() {
    const [tr, cs, mp] = await Promise.all([api("/api/trending"), api("/api/categories"), api("/api/map")]);
    meta(tr);
    const top = tr.items.slice(0, 10);
    const chans = ORDER.map((k) => cs.categories.find((c) => c.key === k)).filter(Boolean);
    const EMO = Object.fromEntries(Object.entries(CATS).map(([k, v]) => [k, v[0]]));
    main.innerHTML = `
      <h1 class="page-h">Өчигдөр дэлхий юуг уншив?</h1>
      <div class="map-key">
        <span><b>Том</b> = олон хүн уншсан</span>
        <span class="scale"><b>Өнгө</b> = ердийнхөөс
          <i style="background:#2a78d6"></i><em>бага</em>
          <i style="background:#eef1f5;outline:1px solid #d5dae3;outline-offset:-1px"></i><em>ердийн</em>
          <i style="background:#f4a3a9"></i><i style="background:#b5222e"></i><em>их шуугиж байна</em></span>
      </div>
      <div class="tmap" id="tmap"></div>
      <h2 class="sub-h">Сэдэв бүрээр</h2>
      <p class="lead">▲ ×3 = ердийн өдрөөс 3 дахин их уншигдсан</p>
      <ul class="picker" aria-label="Сэдэв сонгох">${top.map((t, i) => `
        <li><button class="pick" data-i="${i}" aria-pressed="${i === 0}">${esc(t.title)} ${surge(t.ratio, true)}</button></li>`).join("")}
      </ul>
      <section class="focus" id="focus" aria-live="polite"></section>
      <section class="sec" aria-labelledby="cat-h">
        <h2 id="cat-h">Ангилал бүрээр</h2>
        <div class="cats">${chans.map((c) => `
          <div class="cat">
            <h3>${cat(c.key)}</h3>
            <ul>${c.topics.slice(0, 4).map((t) => `<li><a href="${href(t.article)}">${esc(t.title)}</a><span class="sp" data-a="${esc(t.article)}" data-k="${c.key}"></span>${surge(t.ratio, true)}</li>`).join("")}</ul>
          </div>`).join("")}
        </div>
      </section>`;

    draw(() => C.treemap(document.getElementById("tmap"), mp.items, { emoji: EMO, label: "Өчигдрийн анхаарлын газрын зураг" }));
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
      document.getElementById("focus").innerHTML = focusHTML(t);
      redraws = redraws.filter((f) => f !== fn);
      fn = draw(drawFocus(t));
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
      <p class="lead">Цэнхэр = бодит, улбар шар = таамаг</p>
      <ol class="rows">${tr.items.map((t, i) => `
        <li class="row">
          <span class="rk">${i + 1}</span>
          <div>
            <h3><a href="${href(t.article)}">${esc(t.title)}</a></h3>
            <p class="meta">${surge(t.ratio)}<span><b>${C.fmt(t.views)}</b> уншилт</span><span>3 өдөрт ${pct(t)}</span><span>${cat(t.category)}</span></p>
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
      <section class="focus topic" style="margin-top:14px">${focusHTML(t, { titleTag: "h1", link: false, days: t.history.length })}
        <table class="fc">
          <caption>Ирэх 3 өдрийн таамаг. 80% хүрээг model-ийн өмнөх үеийн бодит алдаанаас тооцоолсон.</caption>
          <thead><tr><th>Өдөр</th><th>Доод</th><th>Таамаг</th><th>Дээд</th></tr></thead>
          <tbody>${t.forecast.map((f) => `<tr><td>${C.longDate(f.d)}</td><td>${C.fmt(f.lo)}</td><td class="y">${C.fmt(f.y)}</td><td>${C.fmt(f.hi)}</td></tr>`).join("")}</tbody>
        </table>
      </section>`;
    draw(drawFocus(t));
  }

  // ═════════ Загвар ═════════
  async function model() {
    const m = await api("/api/model");
    meta(m);
    main.innerHTML = `
      <h1 class="page-h">Загвар хэр сайн таамагладаг вэ?</h1>
      <p class="lead">Энгийн аргуудаас илүү зөв үү?</p>
      <div class="mgrid">
        <div class="mcard">
          <h3>Хэр их алддаг вэ?</h3>
          <p class="chart-sub">Богино = илүү зөв</p>
          <div class="mchart" id="m-bars"></div>
          <ul class="key">
            <li><i class="k-blue"></i>LightGBM</li>
            <li><i style="background:var(--gray-bar)"></i>Өчигдрийнх шиг</li>
            <li><i style="background:var(--gray-bar);opacity:.6"></i>7 хоногийн өмнөх шиг</li>
          </ul>
        </div>
        <div class="mcard">
          <h3>Overfit болсон уу?</h3>
          <p class="chart-sub">Хоёр шугам ойрхон = сайн</p>
          <div class="mchart" id="m-curve"></div>
        </div>
        <div class="mcard" style="grid-column:1/-1">
          <h3>Таамаглахад юу хамгийн их тусалдаг вэ?</h3>
          <p class="chart-sub">Урт = илүү чухал</p>
          <div class="mchart" id="m-imp" style="height:290px"></div>
        </div>
      </div>`;
    draw(() => C.groups(document.getElementById("m-bars"), m.metrics, ["model", "naive", "seasonal"], [], "Model-ийн алдааг энгийн аргуудтай харьцуулсан"));
    draw(() => C.curve(document.getElementById("m-curve"), m.curve, m.best_iter, "Сургалт ба validation алдааны муруй"));
    const FEAT = { lag_1: "Өчигдрийн уншилт", ratio_7: "7 хоногийн дундажтай харьцаа", roll_mean_7: "7 хоногийн дундаж",
      lag_7: "7 хоногийн өмнөх уншилт", growth_3: "Сүүлийн 3 хоногийн өсөлт", dow: "Гараг", roll_std_14: "14 хоногийн хэлбэлзэл",
      category: "Ангилал", lag_14: "14 хоногийн өмнөх уншилт", days_since_peak: "Оргилоос хойш хоног" };
    draw(() => C.hbars(document.getElementById("m-imp"), m.importance.map((r) => ({ ...r, f: FEAT[r.f] || r.f })), "Feature importance"));
  }

  // ═════════ Сонирхолтой ═════════
  async function facts() {
    const d = await api("/api/insights");
    document.getElementById("mock-note").hidden = true;
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
      hi: [0, 3], valLabels: { 0: "100%", 3: `${dec3}%`, 7: `${Math.round(d.decay[7])}%` }, label: "Оргилын дараах өдрүүдэд анхаарал хэдэн хувь үлддэг вэ" }));
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
