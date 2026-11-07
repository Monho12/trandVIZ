// Шуугиан — энгийн hash router + хуудсууд
(function () {
  const C = window.Charts;
  const main = document.getElementById("main");
  const CATS = {
    politics: ["🏛️", "Улс төр"], film_tv: ["🎬", "Кино ба цуврал"], true_crime: ["🕯️", "True crime"],
    tech_ai: ["🤖", "AI ба технологи"], sports: ["⚽", "Спорт"], music: ["🎵", "Хөгжим"],
    games_anime: ["🎮", "Тоглоом ба anime"], celebs: ["💅", "Алдартнууд"], society: ["👥", "Нийгэм"],
    mongolia: ["🇲🇳", "Монгол"], viral: ["🔥", "Вирал"],
  };
  const cat = (k) => (CATS[k] || ["", k]).join(" ");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const href = (a) => "#/topic/" + encodeURIComponent(a);
  const surge = (r) => r >= 1.5
    ? `<span class="x">×${r} хэвийнээс</span>`
    : `<span class="x calm">хэвийн</span>`;
  const change = (t) => {
    const last = t.history[t.history.length - 1].v, y3 = t.forecast[t.forecast.length - 1].y;
    const p = Math.round((y3 / Math.max(last, 1) - 1) * 100);
    return p < 0 ? `↓ ${-p}%` : `↑ ${p}%`;
  };

  // Дэлгэцийн хэмжээ өөрчлөгдөхөд графикуудыг дахин зурна
  let redraws = [];
  let rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => redraws.forEach((f) => f()), 150); });
  const draw = (fn) => { redraws.push(fn); fn(); };

  const cache = {};
  async function api(path) {
    if (!cache[path]) cache[path] = fetch(path).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
    return cache[path];
  }
  function meta(d) {
    document.getElementById("asof").textContent = `Өгөгдөл: ${d.asof} хүртэл`;
    document.getElementById("mock-note").hidden = !d.mock;
  }

  // ───────── Тренд (нүүр) ─────────
  async function trend() {
    const [tr, cs] = await Promise.all([api("/api/trending"), api("/api/categories")]);
    meta(tr);
    const [top, ...rest] = tr.items;
    main.innerHTML = `
      <section class="hero" aria-labelledby="hero-title">
        <div>
          <p class="hero-q">Дэлхий өчигдөр юуг хамгийн их шуугив?</p>
          <h1 class="hero-title" id="hero-title"><a href="${href(top.article)}">${esc(top.title)}</a></h1>
          <p class="hero-facts">
            <span class="f-surge"><b>×${top.ratio}</b> хэвийнээс</span>
            <span><b>${C.fmt(top.views)}</b> уншилт</span>
            <span class="f-cast"><b>${change(top)}</b> 3 хоногт</span>
          </p>
          <div class="hero-chart" id="hero-chart"></div>
          <ul class="legend">
            <li class="lg-hist"><span>сүүлийн 30 хоног</span></li>
            <li class="lg-now"><span>өчигдөр</span></li>
            <li class="lg-cast"><span>таамаг ба 80% бүс</span></li>
          </ul>
        </div>
        <aside class="side" aria-labelledby="side-h">
          <h2 id="side-h">Дараагийнх нь</h2>
          <ol>${rest.slice(0, 8).map((t) => `
            <li><a href="${href(t.article)}">${esc(t.title)}<span class="cat">${cat(t.category)}</span></a>${surge(t.ratio)}</li>`).join("")}
          </ol>
        </aside>
      </section>
      <section class="sec" aria-labelledby="cats-h">
        <h2 id="cats-h">Ангилал бүрээр</h2>
        <p class="sec-lead">Ангилал бүрийн хамгийн их уншигдаж буй сэдвүүд. Жижиг график бүрийн баруун хэсэг нь ирэх 3 өдрийн таамаг.</p>
        <div class="cats">${cs.categories.map((c) => `
          <div class="cat-block">
            <h3>${cat(c.key)}</h3>
            <ul>${c.topics.map((t, i) => `
              <li><a href="${href(t.article)}">${esc(t.title)}</a><div class="spark" data-k="${c.key}" data-i="${i}"></div></li>`).join("")}
            </ul>
          </div>`).join("")}
        </div>
      </section>`;
    draw(() => C.series(document.getElementById("hero-chart"), { ...top, axis: true, pulse: true,
      label: `${top.title}: сүүлийн 30 хоногийн хандалт ба ирэх 3 өдрийн таамаг` }));
    const byKey = Object.fromEntries(cs.categories.map((c) => [c.key, c.topics]));
    draw(() => main.querySelectorAll(".spark").forEach((b) => {
      const t = byKey[b.dataset.k][+b.dataset.i];
      C.series(b, { history: t.history, forecast: t.forecast, label: `${t.title} жижиг график` });
    }));
  }

  // ───────── Шуугиан ─────────
  async function shuugian() {
    const tr = await api("/api/trending");
    meta(tr);
    main.innerHTML = `
      <section class="sec" aria-labelledby="sh-h" style="padding-top:8px">
        <h1 id="sh-h" class="hero-title" style="font-size:clamp(30px,4vw,44px)">Шуугиан</h1>
        <p class="sec-lead">Өчигдөр хамгийн их уншигдсан сэдвүүд, хэвийн хэмжээнээсээ хэд дахин өссөнөөр нь эрэмбэлэв.
          Шугамын шар цэг өчигдрийг, баруун талын зураасан бүс ирэх 3 өдрийн таамгийг заана.</p>
        <ol class="rows">${tr.items.map((t, i) => `
          <li class="row">
            <span class="rk">${i + 1}</span>
            <div>
              <h3><a href="${href(t.article)}">${esc(t.title)}</a></h3>
              <p class="meta">${surge(t.ratio)}<span>${C.fmt(t.views)} уншилт</span><span>${cat(t.category)}</span><span>3 хоногт ${change(t)}</span></p>
            </div>
            <div class="row-chart" data-i="${i}"></div>
          </li>`).join("")}
        </ol>
      </section>`;
    draw(() => main.querySelectorAll(".row-chart").forEach((b) => {
      const t = tr.items[+b.dataset.i];
      C.series(b, { history: t.history, forecast: t.forecast, label: `${t.title}: 30 хоног ба таамаг` });
    }));
  }

  // ───────── Нэг сэдэв ─────────
  async function topic(article) {
    const t = await api("/api/topic/" + encodeURIComponent(article));
    meta(t);
    const h = t.history, med = [...h.slice(-30)].map((p) => p.v).sort((a, b) => a - b)[15];
    main.innerHTML = `
      <section class="sec" style="padding-top:8px" aria-labelledby="t-h">
        <a class="back" href="#/">← Тренд руу буцах</a>
        <p class="hero-q" style="margin-top:24px">${cat(t.category)}</p>
        <h1 id="t-h" class="hero-title" style="font-size:clamp(30px,4.6vw,52px)">${esc(t.title)}</h1>
        <div class="topic-chart" id="topic-chart"></div>
        <dl class="stats">
          <div><dt>Өчигдөр</dt><dd>${C.fmt(t.views)}</dd></div>
          <div><dt>30 хоногийн медиан</dt><dd>${C.fmt(med)}</dd></div>
          <div><dt>Хэвийнээс</dt><dd style="color:var(--surge)">×${t.ratio}</dd></div>
          <div><dt>3 хоногийн дараа</dt><dd style="color:var(--cast)">${change(t)}</dd></div>
        </dl>
        <table class="fc-table">
          <caption class="note" style="text-align:left;caption-side:top;padding-bottom:8px">Ирэх 3 өдрийн таамаг. 80% бүс нь өмнөх үеийн бодит алдаанаас тооцоологдсон.</caption>
          <thead><tr><th>Өдөр</th><th>Доод</th><th>Таамаг</th><th>Дээд</th></tr></thead>
          <tbody>${t.forecast.map((f) => `<tr><td>${f.d}</td><td>${C.fmt(f.lo)}</td><td class="y">${C.fmt(f.y)}</td><td>${C.fmt(f.hi)}</td></tr>`).join("")}</tbody>
        </table>
      </section>`;
    draw(() => C.series(document.getElementById("topic-chart"), { ...t, axis: true, pulse: true,
      label: `${t.title}: 180 хоногийн хандалт ба 3 өдрийн таамаг` }));
  }

  // ───────── Загвар ─────────
  async function model() {
    const m = await api("/api/model");
    meta(m);
    main.innerHTML = `
      <section class="sec" style="padding-top:8px" aria-labelledby="m-h">
        <h1 id="m-h" class="hero-title" style="font-size:clamp(30px,4vw,44px)">Загвар хэр сайн бэ?</h1>
        <p class="sec-lead">Таамаг бүрийг энгийн аргуудтай харьцуулж шалгасан. Model тэднээс сайн биш бол ашиглах утгагүй.</p>
        <div class="mgrid">
          <div>
            <h2>Алдаа (бага байх тусам сайн)</h2>
            <div class="mchart" id="m-bars"></div>
            <p class="note">MAE, log хуваарьт. "Өчигдрийнх шиг" нь маргаашийг өнөөдрийнхтэй адил гэж үздэг. "7 хоногийн өмнөх" нь яг долоо хоногийн өмнөх утгыг давтана.</p>
          </div>
          <div>
            <h2>Overfit болсон уу?</h2>
            <div class="mchart" id="m-curve"></div>
            <p class="note">Саарал нь сургалтын, цэнхэр нь validation алдаа. Validation алдаа буурахаа больсон цэгт (early stop) сургалтыг зогсоосон.</p>
          </div>
          <div style="grid-column:1/-1">
            <h2>Юу хамгийн их нөлөөлж байна?</h2>
            <div class="mchart" id="m-imp" style="height:300px"></div>
            <p class="note">Feature importance (gain). lag_1 = өчигдрийн утга, ratio_7 = 7 хоногийн дундажтай харьцуулсан өсөлт.</p>
          </div>
        </div>
      </section>`;
    draw(() => C.bars(document.getElementById("m-bars"), m.metrics, ["model", "naive", "seasonal"],
      ["LightGBM", "Өчигдрийнх шиг", "7 хоногийн өмнөх"], "Model-ийн алдааг энгийн аргуудтай харьцуулсан график"));
    draw(() => C.curve(document.getElementById("m-curve"), m.curve, m.best_iter, "Сургалт ба validation алдааны муруй"));
    draw(() => C.hbars(document.getElementById("m-imp"), m.importance, "Feature importance"));
  }

  // ───────── Router ─────────
  async function route() {
    redraws = [];
    const h = location.hash.replace(/^#\/?/, "");
    const [page, arg] = h.split("/");
    const name = page === "shuugian" ? "shuugian" : page === "model" ? "model" : page === "topic" ? "topic" : "trend";
    document.querySelectorAll(".nav a").forEach((a) =>
      a.dataset.route === name ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
    main.innerHTML = `<p class="state">Ачаалж байна…</p>`;
    try {
      if (name === "shuugian") await shuugian();
      else if (name === "model") await model();
      else if (name === "topic") await topic(decodeURIComponent(arg || ""));
      else await trend();
    } catch (e) {
      main.innerHTML = `<p class="state">Өгөгдөл ачаалж чадсангүй (${esc(e.message)}). Хуудсыг дахин ачаалж үзнэ үү.</p>`;
    }
    if (name !== "trend") main.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", route);
  route();
})();
