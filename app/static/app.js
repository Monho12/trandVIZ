// Шуугиан — энгийн hash router + хуудсууд.
// Зарчим: нэг дэлгэц = нэг асуулт. Нарийн мэдээлэл зөвхөн хүссэн үед нээгдэнэ.
(function () {
  const C = window.Charts;
  const main = document.getElementById("main");
  const CATS = {
    politics: "🏛️ Улс төр", film_tv: "🎬 Кино, цуврал", true_crime: "🕯️ True crime", tech_ai: "🤖 AI, технологи",
    sports: "⚽ Спорт", music: "🎵 Хөгжим", games_anime: "🎮 Тоглоом, anime", celebs: "💅 Алдартнууд",
    society: "👥 Нийгэм", mongolia: "🇲🇳 Монгол", viral: "🔥 Вирал",
  };
  const SHORT = { politics: "Улс төр", film_tv: "Кино", true_crime: "True crime", tech_ai: "AI", sports: "Спорт",
    music: "Хөгжим", games_anime: "Тоглоом", celebs: "Алдартнууд", society: "Нийгэм", mongolia: "Монгол" };
  const FEAT = { lag_1: "Өчигдрийн уншилт", ratio_7: "7 хоногийн дундажтай харьцаа", roll_mean_7: "7 хоногийн дундаж",
    lag_7: "7 хоногийн өмнөх уншилт", growth_3: "Сүүлийн 3 хоногийн өсөлт", dow: "Гараг", roll_std_14: "14 хоногийн хэлбэлзэл",
    category: "Ангилал", lag_14: "14 хоногийн өмнөх уншилт", days_since_peak: "Оргилоос хойш хэдэн хоног" };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const href = (a) => "#/topic/" + encodeURIComponent(a);
  const lastV = (t) => t.history[t.history.length - 1].v;
  const in3 = (t) => t.forecast[t.forecast.length - 1];
  const change = (t) => Math.round((in3(t).y / Math.max(lastV(t), 1) - 1) * 100);

  let redraws = [], rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => redraws.forEach((f) => f()), 150); });
  const draw = (fn) => { redraws.push(fn); fn(); return fn; };

  const cache = {};
  const api = (p) => (cache[p] ||= fetch(p).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }));
  const mock = (d) => { document.getElementById("mock-note").hidden = !d.mock; };

  // Нэг сэдвийн "түүх": гарчиг → хоёр тоо → график
  function storyHTML(t, { eyebrow, tag = "h2", id, link = true }) {
    const p = change(t);
    const big = t.ratio >= 1.5
      ? `<span class="num">${t.ratio}×</span><span class="lbl">ердийн өдрөөс их уншигдсан</span>`
      : `<span class="num">${C.fmt(t.views)}</span><span class="lbl">уншилт, ердийн хэмжээндээ</span>`;
    const title = link ? `<a href="${href(t.article)}">${esc(t.title)}</a>` : esc(t.title);
    return `
      <p class="eyebrow">${eyebrow}</p>
      <${tag} id="${id}">${title}</${tag}>
      <div class="facts">
        <p class="fact">${big}</p>
        <p class="fact f-cast"><span class="num">${p < 0 ? "↓" : "↑"} ${Math.abs(p)}%</span><span class="lbl">ирэх 3 өдөрт ${p < 0 ? "буурах" : "өсөх"} таамагтай</span></p>
      </div>
      <div class="chart" id="chart"></div>`;
  }
  const drawStory = (t, days) => () => C.story(document.getElementById("chart"), {
    history: t.history.slice(-days), forecast: t.forecast, normal: t.views / Math.max(t.ratio, 0.01),
    label: `${t.title}: сүүлийн ${days} хоногийн өдөр тутмын уншилт ба ирэх 3 өдрийн таамаг` });

  // ═════════ Нүүр ═════════
  async function home() {
    const [tr, cs] = await Promise.all([api("/api/trending"), api("/api/categories")]);
    mock(tr);
    const [top, ...rest] = tr.items;
    const cats = Object.keys(SHORT).filter((k) => cs.categories.some((c) => c.key === k));
    main.innerHTML = `
      <section class="hero" aria-labelledby="hero-t">
        ${storyHTML(top, { eyebrow: `Өчигдөр, ${C.longDate(tr.asof)}, хамгийн их шуугисан`, id: "hero-t" })}
        <a class="more" href="${href(top.article)}">Дэлгэрэнгүй үзэх</a>
      </section>
      <section class="sec" aria-labelledby="also-h">
        <h2 id="also-h">Мөн шуугиж байна</h2>
        <ul class="seg" aria-label="Ангиллаар шүүх">
          <li><button data-k="" aria-pressed="true">Бүгд</button></li>
          ${cats.map((k) => `<li><button data-k="${k}" aria-pressed="false">${SHORT[k]}</button></li>`).join("")}
        </ul>
        <ol class="list" id="list"></ol>
      </section>`;
    draw(drawStory(top, 30));

    const listEl = document.getElementById("list");
    function fill(k) {
      const items = k ? [...(cs.categories.find((c) => c.key === k)?.topics || [])].sort((a, b) => b.ratio - a.ratio) : rest.slice(0, 12);
      listEl.innerHTML = items.length ? items.map((t, i) => `
        <li><a href="${href(t.article)}">
          <span class="rk">${i + 1}</span>
          <span class="t">${esc(t.title)}<span class="c">${CATS[t.category] || ""}</span></span>
          ${t.ratio >= 1.5 ? `<span class="x">${t.ratio}×</span>` : `<span class="x calm">ердийн</span>`}
          <span class="chev" aria-hidden="true">›</span>
        </a></li>`).join("") : `<li class="empty">Энэ ангилалд өгөгдөл алга.</li>`;
    }
    main.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => {
      main.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      fill(b.dataset.k);
    }));
    fill("");
  }

  // ═════════ Нэг сэдэв ═════════
  async function topic(article) {
    const t = await api("/api/topic/" + encodeURIComponent(article));
    mock(t);
    const days = Math.min(90, t.history.length);
    main.innerHTML = `
      <a class="back" href="#/">‹ Нүүр</a>
      <section class="hero" aria-labelledby="t-h">
        ${storyHTML(t, { eyebrow: CATS[t.category] || "", tag: "h1", id: "t-h", link: false })}
        <details class="deep">
          <summary>Таамгийн дэлгэрэнгүй</summary>
          <table class="fc">
            <thead><tr><th>Өдөр</th><th>Таамаг</th><th>Ихэвчлэн энэ хооронд</th></tr></thead>
            <tbody>${t.forecast.map((f) => `<tr><td>${C.longDate(f.d)}</td><td class="y">≈ ${C.fmt(f.y)}</td><td>${C.fmt(f.lo)} – ${C.fmt(f.hi)}</td></tr>`).join("")}</tbody>
          </table>
          <p>"Ихэвчлэн энэ хооронд" нь 80% магадлалтай хүрээ: model өмнө нь хэр зэрэг алддаг байсныг бодит алдаанаас тооцоолсон.</p>
        </details>
      </section>`;
    draw(drawStory(t, days));
  }

  // ═════════ Загвар ═════════
  async function model() {
    const m = await api("/api/model");
    mock(m);
    const avg = (k) => m.metrics.reduce((s, r) => s + r[k], 0) / m.metrics.length;
    const mm = avg("model"), nv = avg("naive"), ss = avg("seasonal");
    const better = Math.round((1 - mm / Math.min(nv, ss)) * 100);
    const imp = m.importance.slice(0, 6).map((r) => ({ ...r, name: FEAT[r.f] || r.f }));
    main.innerHTML = `
      <h1 class="page-h">Загвар хэр зөв бэ?</h1>
      <p class="lead">Өгөгдлийн хамгийн сүүлийн хэсгийг сургалтаас нууж, model-ийг зөвхөн тэр дээр шалгасан.</p>
      <section class="mcard" aria-labelledby="m1">
        <p class="eyebrow">Дундаж алдаа, бага байх тусам сайн</p>
        <h2 id="m1">Энгийн аргуудаас ${better}% бага алддаг</h2>
        <div class="mchart" id="m-cmp" style="height:150px"></div>
        <p class="note">"Өчигдрийнх шиг" нь маргаашийг өнөөдөртэй яг адилхан гэж үздэг хамгийн энгийн арга. Model үүнээс сайн биш бол ашиглах утгагүй.</p>
      </section>
      <section class="mcard" aria-labelledby="m2">
        <p class="eyebrow">Overfit шалгалт</p>
        <h2 id="m2">Шалгалтын алдаа буурахаа больсон үед сургалтыг зогсоосон</h2>
        <div class="mchart" id="m-curve"></div>
        <p class="note">Model сургалтын өгөгдлийг цээжилж эхэлбэл шалгалтын алдаа дахин өсдөг. Тэр мөчөөс өмнө зогсоохыг early stopping гэнэ. Хоёр шугам ойрхон байгаа нь overfit бага гэсэн үг.</p>
      </section>
      <section class="mcard" aria-labelledby="m3">
        <p class="eyebrow">Таамагт юу хамгийн их нөлөөлдөг вэ</p>
        <h2 id="m3">${imp[0].name} хамгийн чухал</h2>
        <div class="mchart" id="m-imp" style="height:200px"></div>
      </section>`;
    draw(() => C.compare(document.getElementById("m-cmp"), [
      { name: "LightGBM", v: mm }, { name: "Өчигдрийнх шиг", v: nv }, { name: "7 хоногийн өмнөх шиг", v: ss },
    ], "Model ба энгийн аргуудын дундаж алдаа"));
    draw(() => C.curve(document.getElementById("m-curve"), m.curve, m.best_iter, "Сургалт ба шалгалтын алдааны муруй"));
    draw(() => C.hbars(document.getElementById("m-imp"), imp, "Хамгийн их нөлөөлдөг 6 хүчин зүйл"));
  }

  // ═════════ Router ═════════
  async function route() {
    redraws = [];
    document.getElementById("tip").hidden = true;
    const [page, arg] = location.hash.replace(/^#\/?/, "").split("/");
    const name = ["model", "topic"].includes(page) ? page : "home";
    document.querySelectorAll(".nav a").forEach((a) =>
      a.dataset.route === name ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
    main.innerHTML = `<p class="state">Ачаалж байна…</p>`;
    try {
      if (name === "model") await model();
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
