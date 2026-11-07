// Шуугиан — шөнийн радио. Энгийн hash router + хуудсууд.
(function () {
  const C = window.Charts;
  const main = document.getElementById("main");
  const CATS = {
    politics: ["🏛️", "Улс төр"], film_tv: ["🎬", "Кино, цуврал"], true_crime: ["🕯️", "True crime"],
    tech_ai: ["🤖", "AI, технологи"], sports: ["⚽", "Спорт"], music: ["🎵", "Хөгжим"],
    games_anime: ["🎮", "Тоглоом, anime"], celebs: ["💅", "Алдартнууд"], society: ["👥", "Нийгэм"],
    mongolia: ["🇲🇳", "Монгол"], viral: ["🔥", "Вирал"],
  };
  const ORDER = ["politics", "film_tv", "true_crime", "tech_ai", "sports", "music", "games_anime", "celebs", "society", "mongolia"];
  const catName = (k) => (CATS[k] || ["", k])[1];
  const catFull = (k) => (CATS[k] || ["", k]).join(" ");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const href = (a) => "#/topic/" + encodeURIComponent(a);
  const freq = (i, n) => (88 + (i + 0.5) * (20 / n)).toFixed(1);   // FM 88–108 хуваарь дээрх байрлал
  const change = (t) => {
    const last = t.history[t.history.length - 1].v, y3 = t.forecast[t.forecast.length - 1].y;
    const p = Math.round((y3 / Math.max(last, 1) - 1) * 100);
    return p < 0 ? `↓ ${-p}%` : `↑ ${p}%`;
  };
  // VU метр: хэвийнээс хэд дахин чанга байгааг 12 гэрлээр. Сүүлийн 3 нь улаан.
  const vu = (ratio, n = 12) => {
    const on = Math.max(1, Math.min(n, Math.round(4 + 2.4 * Math.log2(Math.max(ratio, 0.5)))));
    return `<span class="vu" aria-hidden="true">${Array.from({ length: n }, (_, i) =>
      `<i class="${i < on ? "on" : ""}${i >= n - 3 ? " red" : ""}"></i>`).join("")}</span>`;
  };

  let redraws = [], rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => redraws.forEach((f) => f()), 150); });
  const draw = (fn) => { redraws.push(fn); fn(); };

  const cache = {};
  const api = (p) => (cache[p] ||= fetch(p).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }));
  function meta(d) {
    document.getElementById("asof").textContent = `Дохио: ${d.asof} хүртэл`;
    document.getElementById("mock-note").hidden = !d.mock;
  }

  // ═════════ Эфир (нүүр) ═════════
  async function air() {
    const [tr, cs] = await Promise.all([api("/api/trending"), api("/api/categories")]);
    meta(tr);
    // Тааруулагч дээр станцуудыг цагаан толгойн дарааллаар байрлуулна; зүү хамгийн чанга нь дээр очно
    const st = [...tr.items].sort((a, b) => a.title.localeCompare(b.title));
    const loud = tr.items[0];
    const maxV = Math.max(...st.map((t) => Math.log10(t.views + 1))), minV = Math.min(...st.map((t) => Math.log10(t.views + 1)));
    const chans = ORDER.map((k) => cs.categories.find((c) => c.key === k)).filter(Boolean);

    main.innerHTML = `
      <section aria-labelledby="dial-h">
        <h1 id="dial-h" class="skip">Станц сонгох</h1>
        <div class="dial">
          <div class="dial-scale" id="dial" role="group" aria-label="Станцууд: сум товчоор солино">
            ${st.map((t, i) => `<button class="station${t.ratio >= 3 ? " hot" : ""}" style="left:${((i + 0.5) / st.length) * 100}%"
                data-i="${i}" aria-pressed="false" tabindex="-1" aria-label="${esc(t.title)}, хэвийнээс ×${t.ratio}">
                <i style="height:${18 + 70 * ((Math.log10(t.views + 1) - minV) / Math.max(maxV - minV, 0.01))}%"></i></button>`).join("")}
            <span class="needle" id="needle" aria-hidden="true"></span>
          </div>
          <div class="dial-nums" aria-hidden="true">${[88, 92, 96, 100, 104, 108].map((f) => `<span>${f}</span>`).join("")}</div>
          <p class="dial-hint">Станц бүр нэг сэдэв. Өндөр зураас нь их уншигдсан, улаан нь хэвийнээсээ 3+ дахин чанга. Дарж эсвэл ← → товчоор тааруулна.</p>
        </div>
      </section>
      <section class="onair" id="onair" aria-live="polite"></section>
      <section class="sec" aria-labelledby="mix-h">
        <h2 id="mix-h" class="sec-h">Арван суваг</h2>
        <p class="sec-lead">Ангилал бүр нэг суваг. Метр нь тухайн сувгийн хамгийн чанга сэдэв хэвийн хэмжээнээсээ хэд дахин өссөнийг заана.</p>
        <div class="mixer">${chans.map((c) => {
          const lead = [...c.topics].sort((a, b) => b.ratio - a.ratio)[0];
          const on = Math.max(1, Math.min(14, Math.round(5 + 2.6 * Math.log2(Math.max(lead.ratio, 0.5)))));
          return `<div class="strip">
            <div class="strip-meter" aria-hidden="true">${Array.from({ length: 14 }, (_, i) => `<i class="${i < on ? "on" : ""}${i >= 11 ? " red" : ""}"></i>`).join("")}</div>
            <div class="strip-val${lead.ratio >= 3 ? " red" : ""}">×${lead.ratio}</div>
            <h3><span aria-hidden="true">${CATS[c.key][0]}</span>${catName(c.key)}</h3>
            <ul>${c.topics.slice(0, 3).map((t) => `<li><a href="${href(t.article)}">${esc(t.title)}</a></li>`).join("")}</ul>
          </div>`; }).join("")}
        </div>
      </section>`;

    const dial = document.getElementById("dial"), needle = document.getElementById("needle");
    const btns = [...dial.querySelectorAll(".station")];
    let cur = st.indexOf(loud);

    function placeNeedle() { needle.style.transform = `translateX(${dial.clientWidth * ((cur + 0.5) / st.length) - 1}px)`; }
    function tune(i, focus) {
      cur = (i + st.length) % st.length;
      btns.forEach((b, j) => { b.setAttribute("aria-pressed", j === cur); b.tabIndex = j === cur ? 0 : -1; });
      if (focus) btns[cur].focus();
      placeNeedle();
      const t = st[cur], box = document.getElementById("onair");
      box.classList.remove("tuning"); void box.offsetWidth; box.classList.add("tuning");
      box.innerHTML = `
        <p class="onair-kicker">Одоо ${freq(cur, st.length)} FM эфирт</p>
        <div>
          <h2 class="onair-title"><a href="${href(t.article)}">${esc(t.title)}</a></h2>
          <p class="onair-cat">${catFull(t.category)}</p>
        </div>
        <dl class="readout">
          <div><dt>Хэвийнээс</dt><dd class="${t.ratio >= 1.5 ? "r-clip" : ""}">×${t.ratio}</dd>${vu(t.ratio)}</div>
          <div><dt>Өчигдөр уншсан</dt><dd>${C.fmt(t.views)}</dd></div>
          <div><dt>3 хоногийн дараа</dt><dd class="r-ghost">${change(t)}</dd></div>
        </dl>
        <div class="wave-wrap">
          <div class="wave" id="wave"></div>
          <ul class="wave-legend">
            <li class="wl-sig">сүүлийн 30 хоногийн уншилт, өдөр бүр нэг багана</li>
            <li class="wl-ghost">ирэх 3 өдрийн таамаг, 80% бүсээр</li>
          </ul>
        </div>`;
      redraws = redraws.filter((f) => !f.wave);
      const fn = () => C.wave(document.getElementById("wave"), { ...t, axis: true,
        label: `${t.title}: сүүлийн 30 хоногийн уншилт ба ирэх 3 өдрийн таамаг` });
      fn.wave = true; draw(fn);
    }
    btns.forEach((b) => b.addEventListener("click", () => tune(+b.dataset.i)));
    dial.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight") { e.preventDefault(); tune(cur + 1, true); }
      if (e.key === "ArrowLeft") { e.preventDefault(); tune(cur - 1, true); }
    });
    redraws.push(placeNeedle);
    tune(cur);
  }

  // ═════════ Бүх станц ═════════
  async function list() {
    const tr = await api("/api/trending");
    meta(tr);
    main.innerHTML = `
      <section class="sec" style="padding-top:28px" aria-labelledby="l-h">
        <h1 id="l-h" class="sec-h">Бүх станц</h1>
        <p class="sec-lead">Өчигдөр хамгийн их уншигдсан ${tr.items.length} сэдэв, хэвийн хэмжээнээсээ хэд дахин чанга байгаагаар нь эрэмбэлэв.
          Шар багана бол бодит уншилт, бүдэг ягаан сүүдэр бол ирэх 3 өдрийн таамаг.</p>
        <ol class="tracks">${tr.items.map((t, i) => `
          <li class="track">
            <span class="freq">${freq(i, tr.items.length)}</span>
            <div>
              <h3><a href="${href(t.article)}">${esc(t.title)}</a></h3>
              <p class="cat"><span>${catFull(t.category)}</span><span>${C.fmt(t.views)} уншилт</span><span>3 хоногт ${change(t)}</span></p>
            </div>
            <div class="lvl"><b class="${t.ratio >= 3 ? "red" : ""}">×${t.ratio}</b> хэвийнээс${vu(t.ratio)}</div>
            <div class="mini" data-i="${i}"></div>
          </li>`).join("")}
        </ol>
      </section>`;
    draw(() => main.querySelectorAll(".mini").forEach((b) => {
      const t = tr.items[+b.dataset.i];
      C.wave(b, { history: t.history, forecast: t.forecast, label: `${t.title}: 30 хоног ба таамаг` });
    }));
  }

  // ═════════ Нэг станц ═════════
  async function topic(article) {
    const t = await api("/api/topic/" + encodeURIComponent(article));
    meta(t);
    const s = t.history.slice(-30).map((p) => p.v).sort((a, b) => a - b), med = s[15];
    main.innerHTML = `
      <a class="back" href="#/">← Эфир рүү буцах</a>
      <section class="onair" style="border:0;padding-bottom:0" aria-labelledby="t-h">
        <p class="onair-kicker plain">${catFull(t.category)}</p>
        <div>
          <h1 id="t-h" class="onair-title">${esc(t.title)}</h1>
        </div>
        <dl class="readout">
          <div><dt>Хэвийнээс</dt><dd class="${t.ratio >= 1.5 ? "r-clip" : ""}">×${t.ratio}</dd>${vu(t.ratio)}</div>
          <div><dt>Өчигдөр уншсан</dt><dd>${C.fmt(t.views)}</dd></div>
          <div><dt>Ердийн өдөр (30 хоногийн медиан)</dt><dd>${C.fmt(med)}</dd></div>
          <div><dt>3 хоногийн дараа</dt><dd class="r-ghost">${change(t)}</dd></div>
        </dl>
      </section>
      <div class="topic-wave" id="tw"></div>
      <table class="fc">
        <caption>Ирэх 3 өдрийн таамаг. 80% бүсийг model-ийн өмнөх үеийн бодит алдаанаас тооцоолсон.</caption>
        <thead><tr><th>Өдөр</th><th>Доод</th><th>Таамаг</th><th>Дээд</th></tr></thead>
        <tbody>${t.forecast.map((f) => `<tr><td>${f.d}</td><td>${C.fmt(f.lo)}</td><td class="y">${C.fmt(f.y)}</td><td>${C.fmt(f.hi)}</td></tr>`).join("")}</tbody>
      </table>`;
    draw(() => C.wave(document.getElementById("tw"), { ...t, axis: true, label: `${t.title}: 180 хоногийн уншилт ба 3 өдрийн таамаг` }));
  }

  // ═════════ Загвар ═════════
  async function model() {
    const m = await api("/api/model");
    meta(m);
    main.innerHTML = `
      <section class="sec" style="padding-top:28px" aria-labelledby="m-h">
        <h1 id="m-h" class="sec-h">Загвар хэр сайн сонсдог вэ?</h1>
        <p class="sec-lead">Таамаг бүрийг хоёр энгийн аргатай харьцуулсан. Model тэднээс сайн биш бол ашиглах утгагүй.</p>
        <div class="mgrid">
          <div>
            <h3>Алдаа, бага байх тусам сайн</h3>
            <div class="mchart" id="m-bars"></div>
            <p class="note">MAE, log хуваарьт. "Өчигдрийнх шиг" нь маргаашийг өнөөдөртэй адил гэж үздэг. "7 хоногийн өмнөх" нь яг долоо хоногийн өмнөх утгыг давтана.</p>
          </div>
          <div>
            <h3>Overfit болсон уу?</h3>
            <div class="mchart" id="m-curve"></div>
            <p class="note">Саарал нь сургалтын, шар нь validation алдаа. Validation алдаа буурахаа больсон цэгт сургалтыг зогсоосон (early stopping).</p>
          </div>
          <div style="grid-column:1/-1">
            <h3>Юу хамгийн их нөлөөлж байна?</h3>
            <div class="mchart" id="m-imp" style="height:300px"></div>
            <p class="note">Feature importance (gain). lag_1 нь өчигдрийн утга, ratio_7 нь 7 хоногийн дундажтай харьцуулсан өсөлт.</p>
          </div>
        </div>
      </section>`;
    draw(() => C.bars(document.getElementById("m-bars"), m.metrics, ["model", "naive", "seasonal"],
      ["LightGBM", "Өчигдрийнх шиг", "7 хоногийн өмнөх"], "Model-ийн алдааг энгийн аргуудтай харьцуулсан"));
    draw(() => C.curve(document.getElementById("m-curve"), m.curve, m.best_iter, "Сургалт ба validation алдааны муруй"));
    draw(() => C.hbars(document.getElementById("m-imp"), m.importance, "Feature importance"));
  }

  // ═════════ Router ═════════
  async function route() {
    redraws = [];
    const [page, arg] = location.hash.replace(/^#\/?/, "").split("/");
    const name = ["list", "model", "topic"].includes(page) ? page : "air";
    document.querySelectorAll(".nav a").forEach((a) =>
      a.dataset.route === name ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
    main.innerHTML = `<p class="state">Тааруулж байна…</p>`;
    try {
      if (name === "list") await list();
      else if (name === "model") await model();
      else if (name === "topic") await topic(decodeURIComponent(arg || ""));
      else await air();
    } catch (e) {
      main.innerHTML = `<p class="state">Дохио ирсэнгүй (${esc(e.message)}). Хуудсыг дахин ачаалж үзнэ үү.</p>`;
    }
    if (name !== "air") main.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", route);
  route();
})();
