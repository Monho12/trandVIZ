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
        <div class="tile t-blue"><dt>Өчигдөр уншсан</dt><dd>${C.fmt(t.views)}</dd></div>
        <div class="tile"><dt>Ердийн өдөр</dt><dd>${C.fmt(normal)}<small>өчигдөр ×${t.ratio}</small></dd></div>
        <div class="tile t-orange"><dt>3 өдрийн дараа (таамаг)</dt><dd>≈ ${C.fmt(in3(t).y)}<small>${pct(t)}</small></dd></div>
      </dl>
      <p class="chart-h">Өдөр бүрийн уншилт: сүүлийн ${days} хоног ба ирэх 3 өдөр</p>
      <div class="chart" id="chart"></div>
      <ul class="key">
        <li><i class="k-blue"></i>Бодит уншилт</li>
        <li><i class="k-orange"></i>Таамаг</li>
        <li><i class="k-range"></i>80% магадлалтай хүрээ</li>
      </ul>`;
  }
  const drawFocus = (t) => () => C.columns(document.getElementById("chart"), { ...t, axis: true,
    label: `${t.title}: өдөр бүрийн уншилт ба ирэх 3 өдрийн таамаг` });

  // ═════════ Нүүр ═════════
  async function home() {
    const [tr, cs] = await Promise.all([api("/api/trending"), api("/api/categories")]);
    meta(tr);
    const top = tr.items.slice(0, 10);
    const chans = ORDER.map((k) => cs.categories.find((c) => c.key === k)).filter(Boolean);
    main.innerHTML = `
      <h1 class="page-h">Өчигдөр дэлхий юуг хамгийн их уншив?</h1>
      <p class="lead">Wikipedia-ийн уншилтаар хэвийн хэмжээнээсээ хамгийн их өссөн сэдвүүд. ▲ ×3 гэвэл ердийн өдрөөс 3 дахин их уншигдсан гэсэн үг. Сэдэв сонгоход график солигдоно.</p>
      <ul class="picker" aria-label="Сэдэв сонгох">${top.map((t, i) => `
        <li><button class="pick" data-i="${i}" aria-pressed="${i === 0}">${esc(t.title)} ${surge(t.ratio, true)}</button></li>`).join("")}
      </ul>
      <section class="focus" id="focus" aria-live="polite"></section>
      <section class="sec" aria-labelledby="cat-h">
        <h2 id="cat-h">Ангилал бүрээр</h2>
        <p class="lead">Ангилал бүрийн хамгийн их уншигдсан сэдвүүд.</p>
        <div class="cats">${chans.map((c) => `
          <div class="cat">
            <h3>${cat(c.key)}</h3>
            <ul>${c.topics.slice(0, 4).map((t) => `<li><a href="${href(t.article)}">${esc(t.title)}</a>${surge(t.ratio, true)}</li>`).join("")}</ul>
          </div>`).join("")}
        </div>
      </section>`;

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
      <p class="lead">Өчигдөр хамгийн их уншигдсан ${tr.items.length} сэдэв, хэвийн хэмжээнээсээ хэд дахин өссөнөөр нь эрэмбэлэв.
        Цэнхэр нь сүүлийн 30 хоногийн бодит уншилт, улбар шар нь ирэх 3 өдрийн таамаг.</p>
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
      <p class="lead">Таамаг бүрийг хоёр энгийн аргатай харьцуулсан. Model тэднээс сайн биш бол ашиглах утгагүй.</p>
      <div class="mgrid">
        <div class="mcard">
          <h3>Алдаа: бага байх тусам сайн</h3>
          <div class="mchart" id="m-bars"></div>
          <ul class="key">
            <li><i class="k-blue"></i>LightGBM</li>
            <li><i style="background:var(--gray-bar)"></i>Өчигдрийнх шиг</li>
            <li><i style="background:var(--gray-bar);opacity:.6"></i>7 хоногийн өмнөх шиг</li>
          </ul>
          <p class="note">MAE, log хуваарьт. "Өчигдрийнх шиг" нь маргаашийг өнөөдөртэй адил гэж үздэг энгийн арга.</p>
        </div>
        <div class="mcard">
          <h3>Overfit болсон уу?</h3>
          <div class="mchart" id="m-curve"></div>
          <p class="note">Validation алдаа буурахаа больсон цэгт сургалтыг зогсоосон (early stopping). Хоёр шугам ойрхон байвал overfit бага.</p>
        </div>
        <div class="mcard" style="grid-column:1/-1">
          <h3>Таамагт юу хамгийн их нөлөөлдөг вэ?</h3>
          <div class="mchart" id="m-imp" style="height:290px"></div>
          <p class="note">Feature importance (gain). lag_1 нь өчигдрийн утга, ratio_7 нь 7 хоногийн дундажтай харьцуулсан өсөлт.</p>
        </div>
      </div>`;
    draw(() => C.groups(document.getElementById("m-bars"), m.metrics, ["model", "naive", "seasonal"], [], "Model-ийн алдааг энгийн аргуудтай харьцуулсан"));
    draw(() => C.curve(document.getElementById("m-curve"), m.curve, m.best_iter, "Сургалт ба validation алдааны муруй"));
    draw(() => C.hbars(document.getElementById("m-imp"), m.importance, "Feature importance"));
  }

  // ═════════ Router ═════════
  async function route() {
    redraws = [];
    document.getElementById("tip").hidden = true;
    const [page, arg] = location.hash.replace(/^#\/?/, "").split("/");
    const name = ["list", "model", "topic"].includes(page) ? page : "home";
    document.querySelectorAll(".nav a").forEach((a) =>
      a.dataset.route === name ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
    main.innerHTML = `<p class="state">Ачаалж байна…</p>`;
    try {
      if (name === "list") await list();
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
