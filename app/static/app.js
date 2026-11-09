// Шуугиан — нэг хуудас: API-аас өгөгдөл аваад хэсэг бүрийн графикийг зурна.
// Бүтэц, товч, tab, хөдөлгөөнийг kit (assets/system.js, motion.js) хариуцна; энд зөвхөн өгөгдөл ба график.
(function () {
  const C = window.Charts;
  const CATS = {
    politics: "Улс төр", film_tv: "Кино, цуврал", true_crime: "True crime", tech_ai: "AI, технологи",
    sports: "Спорт", music: "Хөгжим", games_anime: "Тоглоом, anime", celebs: "Алдартнууд",
    society: "Нийгэм", mongolia: "Монгол", viral: "Вирал сэдэв",
  };
  const MN = { "Genghis Khan": "Чингис хаан", Mongolia: "Монгол Улс", "Mongol Empire": "Монголын эзэнт гүрэн",
    "Kublai Khan": "Хубилай хаан", "Golden Horde": "Алтан Орд", Ulaanbaatar: "Улаанбаатар", Mongols: "Монголчууд", "Ögedei Khan": "Өгөдэй хаан" };
  const FEAT = { lag_1: "Өчигдрийн уншилт", ratio_7: "7 хоногийн дундажтай харьцаа", roll_mean_7: "7 хоногийн дундаж",
    lag_7: "7 хоногийн өмнөх уншилт", growth_3: "3 хоногийн өсөлт", growth_1: "1 хоногийн өсөлт", dow: "Гараг",
    roll_std_14: "14 хоногийн хэлбэлзэл", category: "Ангилал", lag_14: "14 хоногийн өмнөх", days_since_peak: "Оргилоос хойш хоног",
    vs_level: "Жилийн түвшнээс зөрүү" };
  const cat = (k) => CATS[k] || k;
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const $ = (id) => document.getElementById(id);
  const last = (t) => t.history[t.history.length - 1].v;
  const in3 = (t) => t.forecast[t.forecast.length - 1];
  const md = (s) => { const [, m, d] = s.split("-"); return `${+m}/${+d}`; };

  // Цонхны хэмжээ өөрчлөгдөхөд бүх графикийг дахин зурна (150ms хүлээгээд)
  const redraws = [];
  let rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => redraws.forEach((f) => f()), 150); });
  const draw = (fn) => { redraws.push(fn); fn(); };
  // Нуугдсан (hidden) хүрээнд хэмжээ 0 тул tab нээгдэх үед зурна
  const whenShown = (box, fn) => {
    const run = () => { if (box.offsetParent !== null || box.getClientRects().length) fn(); };
    new MutationObserver(run).observe(box, { attributes: true, attributeFilter: ["hidden"] });
    draw(run);
  };
  const api = (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(p + " " + r.status); return r.json(); });

  let selectTopic = () => {};
  async function main() {
    await document.fonts.ready;                       // шошгын өргөнийг зөв хэмжихийн тулд фонтыг хүлээнэ
    const [tr, cs, mp, ins, mo] = await Promise.all(
      ["/api/trending", "/api/categories", "/api/map", "/api/insights", "/api/model"].map(api));

    // Огноо, жишээ өгөгдлийн тэмдэглэл
    document.querySelectorAll("[data-asof]").forEach((e) => (e.textContent = `Өгөгдөл ${md(tr.asof)} хүртэл`));
    document.querySelectorAll("[data-asof-short]").forEach((e) => (e.textContent = md(tr.asof)));
    document.querySelectorAll("[data-mock]").forEach((e) => (e.hidden = !tr.mock));

    // 1. Hero: өчигдрийн анхаарлын газрын зураг
    // Нүдэн дээр дарвал тэр сэдэв таамгийн жагсаалтад байвал сонгож, тийш гүйлгэнэ
    const pickFromMap = (article) => {
      const i = tr.items.findIndex((t) => t.article === article);
      if (i < 0) return;
      selectTopic(i);
      document.getElementById("tamag").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    };
    draw(() => C.treemap($("tmap"), mp.items, { onPick: pickFromMap }));

    // 2. App-frame: сэдвийн жагсаалт + сонгосон сэдэв
    const items = tr.items;
    $("topics").innerHTML = items.map((t, i) => `
      <li><button class="topic" type="button" data-i="${i}" aria-pressed="${i === 0}">
        <span class="topic__t"><b>${esc(t.title)}</b><span>${cat(t.category)}</span></span>
        <span class="topic__v">${C.fmt(t.views)}</span>
        ${t.ratio >= 1.5 ? `<span class="chip chip--up">×${t.ratio}</span>` : `<span class="chip">хэвийн</span>`}
      </button></li>`).join("");
    $("o-select").innerHTML = items.map((t, i) => `<option value="${i}">${esc(t.title)}</option>`).join("");
    const btns = [...document.querySelectorAll(".topic")];
    let cur = 0;
    function select(i) {
      cur = i;
      const t = items[i], normal = t.views / Math.max(t.ratio, 0.01);
      const p = Math.round((in3(t).y / Math.max(last(t), 1) - 1) * 100);
      btns.forEach((b, j) => b.setAttribute("aria-pressed", String(j === i)));
      $("o-select").value = String(i);
      $("o-cat").textContent = cat(t.category);
      $("o-title").textContent = t.title;
      $("o-now").textContent = C.fmt(t.views);
      $("o-norm").innerHTML = `${C.fmt(normal)}${t.ratio >= 1.5 ? `<small>×${t.ratio}</small>` : ""}`;
      $("o-cast").innerHTML = `≈ ${C.fmt(in3(t).y)}<small>${p < 0 ? `↓ ${-p}%` : `↑ ${p}%`}</small>`;
      drawOpen();
    }
    const drawOpen = () => {
      const t = items[cur];
      C.columns($("o-chart"), { ...t, axis: true, normal: t.views / Math.max(t.ratio, 0.01),
        label: `${t.title}: өдөр бүрийн уншилт ба ирэх 3 өдрийн таамаг` });
    };
    redraws.push(drawOpen);
    btns.forEach((b) => b.addEventListener("click", () => select(+b.dataset.i)));
    // Жагсаалтын цонхонд бүтэн багтах мөрүүдийг л харуулна; бүх 20 сэдэв дээрх сонгогчид бий
    draw(() => {
      const pane = document.querySelector(".app__pane--list"), lis = [...$("topics").children];
      lis.forEach((li) => (li.hidden = false));
      const bottom = pane.getBoundingClientRect().bottom - 4;
      lis.forEach((li) => (li.hidden = li.getBoundingClientRect().bottom > bottom));
    });
    $("o-select").addEventListener("change", (e) => select(+e.target.value));
    select(0);
    selectTopic = select;

    // 3. Ангилал: нийт уншилтын багана + шилдэг 4 ангиллын карт
    const totals = ins.categories;
    draw(() => C.hbarsV($("c-bars"), totals.map((c) => ({ name: cat(c.key), v: c.views })),
      { fmt: C.fmt, hiN: 2, label: "Ангилал бүрийн сүүлийн 30 хоногийн уншилт" }));
    const byKey = Object.fromEntries(cs.categories.map((c) => [c.key, c.topics]));
    document.querySelectorAll("[data-catcard]").forEach((card) => {
      const k = totals[+card.dataset.catcard].key, top = (byKey[k] || [])[0];
      card.querySelector("[data-t]").textContent = `${cat(k)} ангилал`;
      card.querySelector("[data-p]").textContent = top ? `Өчигдөр хамгийн их: ${top.title}, ${C.fmt(top.views)}.` : "";
      if (top) draw(() => C.columns(card.querySelector("[data-c]"), { history: top.history, label: `${top.title}: 30 хоногийн уншилт` }));
    });

    // 4. Баримтууд (tab бүрийн график)
    const dec3 = Math.round(ins.decay[3]);
    $("f-dec3").textContent = dec3 + "%";
    whenShown($("sc-1"), () => C.bars($("sc-1"), ins.decay, {
      labels: ins.decay.map((_, i) => (i === 0 ? "оргил" : [3, 7, 14].includes(i) ? `${i} хоног` : "")),
      hi: [0, 3], valLabels: { 0: "100%", 3: `${dec3}%`, 7: `${Math.round(ins.decay[7])}%` },
      label: "Оргилын дараах өдрүүдэд анхаарал хэдэн хувь үлддэг вэ" }));
    const DAYS = ["Да", "Мя", "Лх", "Пү", "Ба", "Бя", "Ня"];
    const pick = [["tech_ai", "Ажлын өдөр"], ["sports", "Ням гараг"], ["true_crime", "Амралтын өдөр"], ["film_tv", "Ням гараг"]];
    $("f-week").innerHTML = pick.map(([k, when]) =>
      `<div class="mini-b"><p>${cat(k)}</p><div class="viz-fill" data-k="${k}"></div><p class="mini-s">${when}</p></div>`).join("");
    whenShown($("sc-2"), () => $("f-week").querySelectorAll("[data-k]").forEach((b) => {
      const v = ins.weekday[b.dataset.k], mx = v.indexOf(Math.max(...v));
      C.bars(b, v, { labels: DAYS, hi: [mx], base: 100, minY: 70, label: `${cat(b.dataset.k)}: гарагаар` });
    }));
    whenShown($("sc-3"), () => C.lines($("f-hol"), ins.holidays.months, ins.holidays.series, { label: "Баярын нийтлэлүүдийн сар бүрийн уншилт" }));
    $("f-mn").textContent = Math.round(ins.mongolia[0].share) + "%";
    whenShown($("sc-4"), () => C.hbarsV($("sc-4"), ins.mongolia.map((r) => ({ name: MN[r.title] || r.title, v: r.share })),
      { fmt: (v) => Math.round(v) + "%", hiN: 1, label: "Монголын сэдвүүдийн эзлэх хувь" }));

    // 5. Загвар
    // log хуваарийн MAE-г хувь болгоно: exp(MAE) − 1 ≈ таамаг бодитоос дунджаар хэдэн хувь зөрдөг
    const pctErr = (m) => (Math.exp(m) - 1) * 100;
    const DAYN = ["Маргааш", "2 дахь өдөр", "3 дахь өдөр"];
    draw(() => C.compare($("m-bars"), mo.metrics.map((r) => ({ name: DAYN[r.h - 1], model: pctErr(r.model), naive: pctErr(r.naive) })),
      "Таамгийн дундаж алдаа хувиар: LightGBM ба өчигдрийнх шиг гэсэн энгийн арга"));
    draw(() => C.curve($("m-curve"), mo.curve, mo.best_iter, "Сургалт ба validation алдааны муруй"));
    draw(() => C.flow($("m-flow"), { label: "Wikipedia-гийн уншилт 19 feature болж, гурван LightGBM загвар маргааш, 2 дахь, 3 дахь өдрийг тусдаа таамаглана" }));
    draw(() => C.hbars($("m-imp"), mo.importance.slice(0, 7).map((r) => ({ ...r, f: FEAT[r.f] || r.f })), "Feature importance"));
  }

  main().catch((e) => {
    console.error(e);
    document.querySelectorAll(".chart, .viz").forEach((b) => (b.innerHTML = `<p class="t-small muted">Өгөгдөл ачаалж чадсангүй. Хуудсыг дахин ачаална уу.</p>`));
  });
})();
