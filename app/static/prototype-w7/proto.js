// PROTOTYPE — throwaway (W7 #52, 1-р шат: бүтэц). Production-д холбогдохгүй. Тест, error handling, abstraction зориуд бага.
// Хуудсууд: нүүр (хувилбар а / г), сэдвийн хуудас (3б), Бүх сэдэв, Нотолгоо. Toggle-ууд GROUPS-д, анхдагч = эхний сонголт (UI grill-ийн санал).
(function () {
  const W = window.Words, NS = "http://www.w3.org/2000/svg";
  const main = document.getElementById("main"), tipEl = document.getElementById("tip");
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fmt = (v) => {
    v = Math.round(v);
    if (v >= 1e6) return (v / 1e6).toFixed(v >= 1e7 ? 0 : 1).replace(/\.0$/, "") + " сая";
    if (v >= 1e3) return (v / 1e3).toFixed(v >= 1e4 ? 0 : 1).replace(/\.0$/, "") + " мянга";
    return String(v);
  };
  const pctText = (p) => (p == null ? "—" : `${p > 0 ? "+" : p < 0 ? "−" : ""}${Math.round(Math.abs(p) * 100)}%`);
  const arrowOf = (p) => (p <= -0.1 ? "↘" : p >= 0.1 ? "↗" : "≈");   // ADR 0026: ↓-г ↘-д нэгтгэнэ
  const tenths = (r) => Math.round(r * 10);
  const href = (a) => "#/topic/" + encodeURIComponent(a);
  const md = W.md, longDate = W.longDate;
  const addDays = (iso, n) => { const d = new Date(iso + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };

  // ═════════ Variant panel-ийн toggle-ууд (анхдагч = эхнийх) ═════════
  const GROUPS = [
    { id: "home-card", name: "Нүүр: карт", items: [
      { k: "mark", name: "Anomaly тэмдэг (ADR 0024)", opts: [["short", "● ×3"], ["word", "● огцом ×3"]] },
      { k: "btn", name: "Дэлгэрэнгүйн товч (ADR 0027)", opts: [["cond", "Ямар нөхцөлд?"], ["basis", "Юунд үндэслэсэн бэ?"]] },
      { k: "strength", name: "Хүчтэй өсөлтийн таамаг (ADR 0026)", opts: [["bold", "↗ +40% тод"], ["word", "↗ +40% · хүчтэй"]] },
      { k: "cycle", name: "Мөчлөгийн үг (ADR 0026)", opts: [["every", "долоо хоног бүр ийм"], ["normal", "долоо хоногийн хэвийн өсөлт"]] },
      { k: "link", name: "Картын холбоос (ADR 0027)", opts: [["name", "Зөвхөн нэр"], ["stretch", "Бүх карт (stretched link)"]] },
      { k: "expand", name: "3а дэлгэгдэх (ADR 0027)", opts: [["many", "Зэрэг олон"], ["accordion", "Accordion"]] },
    ] },
    { id: "home-layout", name: "Нүүр: бүтэц, treemap", items: [
      { k: "h1", name: "h1 (ADR 0022)", opts: [["one", "Нэг h1"], ["split", "h1 + lead"]] },
      { k: "sparktext", name: "Spark-ийн текст нөөц (ADR 0027)", opts: [["off", "Зөвхөн band"], ["on", "Band + \"−5…+20%\""]] },
      { k: "cats", name: "Ангиллын картууд (ADR 0027)", opts: [["off", "Нүүрнээс хасах"], ["on", "Үлдээх"]] },
      { k: "tmtap", name: "Treemap-ийн нүд дарахад (ADR 0027)", opts: [["cond", "Карт байвал карт руу, үгүй бол хуудас"], ["page", "Үргэлж хуудас (+ scroll-linked)"]] },
      { k: "tmdot", name: "Бараан нүдэн дээрх ● (ADR 0028)", opts: [["halo", "Цагаан halo"], ["invert", "Урвуу (цагаан ●)"]] },
    ] },
    { id: "topic-chart", name: "Сэдвийн хуудас: гол график", items: [
      { k: "mainmark", name: "Mark (ADR 0027)", opts: [["line", "Шугам + band"], ["bars", "Багана (харьцуулалт)"]] },
      { k: "base", name: "Суурь цонх t−59…t−7", opts: [["on", "Бүдэг дэвсгэр"], ["off", "Тэмдэглэхгүй"]] },
      { k: "range", name: "60/180 сэлгэгч", opts: [["on", "Байна"], ["off", "Байхгүй (60 л)"]] },
      { k: "area180", name: "180 хоног, багана горимд, утсанд", opts: [["area", "Area"], ["line", "Шугам"]] },
      { k: "split", name: "Түүх / таамгийн зааг (ADR 0026)", opts: [["line", "Нимгэн босоо шугам"], ["bg", "Таамгийн хэсгийн дэвсгэр"]] },
    ] },
    { id: "topic-replay", name: "Сэдвийн хуудас: replay, мөчлөг", items: [
      { k: "replaybar", name: "Replay, багана горимд (ADR 0026)", opts: [["outline", "Outline багана"], ["tick", "Хэвтээ tick"]] },
      { k: "cyclemark", name: "Мөчлөг графикт (зөвхөн h3)", opts: [["none", "Тэмдэггүй"], ["tick", "h3 хэвтээ tick"], ["label", "h3 шошго"]] },
    ] },
    { id: "nav", name: "Цэс", items: [
      { k: "navname", name: "Цэсний нэр (expectation test)", opts: [["notolgoo", "Нотолгоо"], ["prev", "Өмнөх таамаг"], ["reliab", "Найдвартай байдал"]] },
      { k: "navlayout", name: "Гар утсан дээр", opts: [["wrap", "flex-wrap ≥ 44px"], ["tabbar", "Доод tab bar"]] },
    ] },
  ];
  const DEF = Object.fromEntries(GROUPS.flatMap((g) => g.items.map((i) => [i.k, i.opts[0][0]])));
  const VARIANTS = [["a", "(а) treemap доод хэсэгт"], ["g", "(г) намхан treemap картын хажууд"]];
  const CASES = [
    ["normal", "Хэвийн: 11.10 (Мягмар), ×10+ оргилтой сэдвүүд"],
    ["friday", "Баасан гарагийн asof: 11.06"],
    ["allfade", "\"Үргэлжлэх\" 0: 2025.11.16"],
    ["quiet", "Нам гүм: Anomaly 0 (зохиомол, 11.10-аас)"],
    ["incomplete", "Өгөгдөл дутуу: 11.10 дутуу, 11.09-ийг харуулна"],
    ["cold", "Cold start: сервер сэрж байна (хүлээлт)"],
    ["error", "API алдаа: бүх хүсэлт"],
    ["partial", "API алдаа: /api/trending л, treemap ажиллана"],
  ];
  const NAVNAME = { notolgoo: "Нотолгоо", prev: "Өмнөх таамаг", reliab: "Найдвартай байдал" };

  // ═════════ State (URL-д: ?v=a&case=normal&o=k.v~k.v) ═════════
  const S = { v: "a", case: "normal", o: { ...DEF }, cold: 20, retryOk: true };
  (function fromURL() {
    const q = new URLSearchParams(location.search);
    if (VARIANTS.some(([k]) => k === q.get("v"))) S.v = q.get("v");
    if (CASES.some(([k]) => k === q.get("case"))) S.case = q.get("case");
    if (q.get("cold")) S.cold = Math.max(1, +q.get("cold") || 20);
    (q.get("o") || "").split("~").filter(Boolean).forEach((p) => { const [k, v] = p.split("."); if (k in DEF) S.o[k] = v; });
  })();
  function toURL() {
    const q = new URLSearchParams();
    q.set("v", S.v); q.set("case", S.case);
    if (S.case === "cold") q.set("cold", S.cold);
    const o = Object.keys(DEF).filter((k) => S.o[k] !== DEF[k]).map((k) => `${k}.${S.o[k]}`).join("~");
    if (o) q.set("o", o);
    history.replaceState(null, "", `${location.pathname}?${q}${location.hash}`);
  }
  const O = (k) => S.o[k];

  // ═════════ Өгөгдөл: fixture + зохиомол cold start / алдаа ═════════
  const files = {};
  const getFile = (n) => (files[n] ||= fetch(`data/${n}.json`).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }));
  let coldUntil = 0, failLeft = 0;
  function resetSim() {
    coldUntil = S.case === "cold" ? Date.now() + S.cold * 1000 : 0;
    failLeft = S.case === "error" || S.case === "partial" ? 1 : 0;
  }
  const apiError = (path) => Object.assign(new Error("503"), { status: 503, path });
  async function data(what) {   // what: "trending" | "map" | "topic" | "track"
    if (Date.now() < coldUntil) await new Promise((r) => setTimeout(r, coldUntil - Date.now()));
    if (failLeft > 0) {
      if (S.case === "error" || (S.case === "partial" && what === "trending")) throw apiError(`/api/${what === "track" ? "track-record" : what}`);
    }
    const track = await getFile("track_record");
    if (what === "track") return track;
    const file = { friday: "friday", allfade: "allfade", incomplete: "incomplete" }[S.case] || "normal";
    const d = await getFile(file);
    return S.case === "quiet" ? quiet(d) : d;
  }
  function quiet(d) {   // Anomaly 0-тэй өдөр valid дээр ажиглагдаагүй (#54): 11.10-ийн өгөгдлөөс anomaly-г арилгасан зохиомол
    if (d._quiet) return d._quiet;
    const strip = (i) => ({ ...i, anomaly: false, verdict: null, verdict_label: null, verdict_track: null });
    const tr = { ...d.trending, anomalies: { n: 0, continue: 0, fade: 0, all_fade: false }, items: d.trending.items.map(strip) };
    return (d._quiet = { ...d, trending: tr, map: { ...d.map, items: d.map.items.map(strip) },
      topics: Object.fromEntries(Object.entries(d.topics).map(([k, t]) => [k, { ...strip(t), anom: [] }])) });
  }
  const trackVer = (tr) => tr.sources.find((s) => s.current) || tr.sources[0];
  const provText = (src) => `${src.source} · model ${src.model_version}`;

  function meta(tr) {
    document.getElementById("asof").textContent = `Өгөгдөл: ${longDate(tr.asof)} хүртэл`;
    const s = document.getElementById("stale-note");
    s.hidden = S.case !== "incomplete";
    if (!s.hidden) s.innerHTML = `<span>${md(addDays(tr.asof, 1))}-ны өгөгдөл дутуу ирсэн. ${md(tr.asof)}-ний дүнг харуулж байна.</span>`;
  }

  // ═════════ Тэмдэг, үг (ADR 0024, 0026) ═════════
  const strong = (t, T) => t.measurable && t.pct != null && t.pct >= T && !t.cyclical;
  const cycWord = () => (O("cycle") === "every" ? "долоо хоног бүр ийм" : "долоо хоногийн хэвийн өсөлт");
  function fcHTML(t, T) {
    const b = strong(t, T);
    const num = `<span class="num${b ? " bold" : ""}">${arrowOf(t.pct)} ${pctText(t.pct)}${b && O("strength") === "word" ? " · хүчтэй" : ""}</span>`;
    const cyc = t.cyclical ? `<span class="cyc" title="${esc(`Энэ гарагуудад ердийн долоо хоногт ${pctText(t.cycle)} өөрчлөгддөг`)}">· ${cycWord()}</span>` : "";
    return cyc ? `${num} ${cyc}` : num;
  }
  function verdictHTML(t, T) {
    const w = t.verdict === "continue" ? `<span class="w bold">үргэлжлэх</span>` : t.verdict === "fade" ? `<span class="w">унтрах</span>` : "";
    return `${w} ${fcHTML(t, T)}`;
  }
  function markHTML(t, asof) {
    if (!t.anomaly) return "";
    const r = t.ratio != null ? `×${t.ratio}` : "";
    const tip = `${longDate(asof)}-нд анхаарал ердийнхөөс ${r || "огцом"} өссөн`;
    return `<span class="dot-mark" title="${esc(tip)}"><i aria-hidden="true">●</i>${O("mark") === "word" || !r ? "огцом " : ""}${r}<span class="vh">: ${esc(tip)}</span></span>`;
  }
  const btnLabel = () => (O("btn") === "cond" ? "Ямар нөхцөлд?" : "Юунд үндэслэсэн бэ?");
  const CODE_TEXT = {
    after_peak: "Сүүлийн 7 хоногт огцом өссөн өдөр байсан. Сүүлийн өдрийн уншилт тэр оргилоос доогуур байна.",
    growing: "Уншилт 7 хоногийн дунджаасаа дээгүүр, 3 өдрийн өмнөхөөсөө өндөр байна.",
    cycle: "Энэ гарагуудад уншилт ердийн долоо хоногт ийм өөрчлөгддөг.",
    rebound: "Огцом өсөөгүй. Уншилт 7 хоногийн дунджаасаа доош орсон байна.",
    total: "Тэр өдөр англи Wikipedia-ийн нийт уншилт ердийнхөөс огцом зөрсөн.",
    unclear: "Дээрх нөхцлүүдийн аль нь ч ажиглагдаагүй.",
  };
  const DISCLAIM = "Энэ нь таамгийн шалтгаан биш. Ийм үед өмнө нь юу болж байсныг харуулна.";
  function iaHTML(rate, text, base) {
    const n = tenths(rate);
    return `<span class="ia-sq${base ? " base" : ""}" aria-hidden="true">${Array.from({ length: 10 }, (_, i) => `<i class="${i < n ? "on" : ""}"></i>`).join("")}</span>
      <span class="ia-t">${text}</span>`;
  }
  // Нөхцөл байдлын track record (ADR 0020): Anomaly-д "≥ 10% буурсан", бусдад "бодит илүүдэл ≥ +10%"
  function codeTrack(t, src) {
    const c = src.by_code.find((x) => x.key === t.situation);
    if (!c || !c.enough) return `<p>Ийм нөхцөлийн өмнөх тохиолдол хангалтгүй (n &lt; ${src.min_n}).</p>`;
    const fade = t.anomaly;
    const v = fade ? c.down10 : c.excess10, b = fade ? src.base.down10 : src.base.excess10;
    const what = fade ? "3 өдрийн дараа ≥ 10% буурсан" : "3 өдрийн дараа долоо хоногийн ердийнхөөс ≥ 10% илүү өссөн";
    return `<div class="ia">${iaHTML(v, `<b>10-аас ${tenths(v)}</b> нь ${what}`)}${iaHTML(b, `10-аас ${tenths(b)}: ердийн үед (бүх сэдэв)`, true)}</div>
      <p class="prov">${esc(provText(src))} · n ${c.n.toLocaleString("en").replace(/,/g, " ")}</p>`;
  }
  function detailHTML(t, src) {
    return `<p class="code">${esc(t.situation_label)}</p><p>${esc(CODE_TEXT[t.situation] || "")}</p>${codeTrack(t, src)}<p class="disclaim">${DISCLAIM}</p>`;
  }

  // ═════════ SVG ═════════
  const el = (tag, attrs = {}, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  };
  function svg(box, label) {
    box.innerHTML = "";
    const w = box.clientWidth, h = box.clientHeight;
    const s = el("svg", { class: "ch", viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": label }, box);
    const defs = el("defs", {}, s), p = el("pattern", { id: "hatch", width: 4, height: 4, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
    el("rect", { width: 1.5, height: 4, fill: "var(--data-fc)" }, p);
    return { s, w, h };
  }
  const niceMax = (m) => { const e = 10 ** Math.floor(Math.log10(m || 1)), f = m / e; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * e; };
  const poly = (pts) => pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("");

  // Tooltip: tap / hover / focus, Esc ба гадна tap-аар хаагдана (ADR 0027, WCAG 1.4.13)
  let tipOwner = null;
  function showTip(html, x, y, owner) {
    tipEl.innerHTML = html; tipEl.hidden = false; tipOwner = owner;
    const r = tipEl.getBoundingClientRect();
    let left = x + 14, top = y - r.height - 12;
    if (left + r.width > innerWidth - 8) left = x - r.width - 14;
    if (left < 8) left = 8;
    if (top < 8) top = y + 18;
    tipEl.style.left = left + "px"; tipEl.style.top = top + "px";
  }
  function hideTip() { tipEl.hidden = true; if (tipOwner && tipOwner.clear) tipOwner.clear(); tipOwner = null; }
  addEventListener("keydown", (e) => { if (e.key === "Escape") hideTip(); });
  document.addEventListener("pointerdown", (e) => { if (tipOwner && !tipOwner.box.contains(e.target)) hideTip(); });
  addEventListener("scroll", () => { if (tipOwner && tipOwner.kind === "spark") hideTip(); }, { passive: true });

  // Spark: 14 өдөр + 3 өдрийн таамаг band-тай, ● Anomaly өдөр. y 0-ээс, сэдэв бүр өөрийн масштаб (ADR 0027)
  function spark(box, t) {
    const hist = t.history.slice(-14), fc = t.forecast, H = hist.length;
    const label = `${t.title}: сүүлийн 14 өдрийн уншилт, ${md(hist[H - 1].d)}-нд ${fmt(hist[H - 1].v)}. ${md(fc[2].d)}-нд ≈ ${fmt(fc[2].y)} гэж таамагласан, 80% магадлалтай ${fmt(fc[2].lo)}–${fmt(fc[2].hi)}.`;
    const { s, w, h } = svg(box, label);
    const pad = { l: 2, r: 4, t: 6, b: 4 }, N = H + 3;
    const max = Math.max(...hist.map((d) => d.v), ...fc.map((f) => f.hi)) * 1.05 || 1;
    const X = (i) => pad.l + (i / (N - 1)) * (w - pad.l - pad.r), Y = (v) => h - pad.b - (v / max) * (h - pad.t - pad.b);
    if (O("split") === "bg") el("rect", { class: "fc-bg", x: X(H - 1), y: 0, width: X(N - 1) - X(H - 1) + pad.r, height: h }, s);
    const last = [X(H - 1), Y(hist[H - 1].v)];
    el("path", { class: "band", d: poly([last, ...fc.map((f, i) => [X(H + i), Y(f.hi)]), ...fc.map((f, i) => [X(H + i), Y(f.lo)]).reverse()]) + "Z" }, s);
    el("path", { class: "act", d: poly(hist.map((d, i) => [X(i), Y(d.v)])) }, s);
    el("path", { class: "fc", d: poly([last, ...fc.map((f, i) => [X(H + i), Y(f.y)])]) }, s);
    if (O("split") === "line") el("line", { class: "split", x1: X(H - 1), x2: X(H - 1), y1: 2, y2: h }, s);
    const an = new Set((t.anom || []).map((a) => a.d));
    hist.forEach((d, i) => { if (an.has(d.d)) el("circle", { class: "dot", cx: X(i), cy: Y(d.v), r: 3.5 }, s); });
    box.dataset.bandPx = (Y(fc[2].lo) - Y(fc[2].hi)).toFixed(1);
  }

  // ═════════ Нүүр ═════════
  const slug = (a) => "c-" + a.replace(/[^A-Za-z0-9]/g, "_");
  function cardHTML(t, ctx) {
    const id = slug(t.article), stretch = O("link") === "stretch";
    const iv = O("sparktext") === "on" && t.interval ? `<p class="c-iv">80% магадлалтай: ${pctText(t.interval.lo)}…${pctText(t.interval.hi)}</p>` : "";
    return `<li class="card${stretch ? " stretch" : ""}" id="${id}" data-a="${esc(t.article)}">
      <div class="c-top"><h3 class="c-name"><a href="${href(t.article)}">${esc(t.title)}</a></h3>${markHTML(t, ctx.asof)}</div>
      <p class="c-verdict">${t.verdict ? verdictHTML(t, ctx.T) : fcHTML(t, ctx.T)}</p>${iv}
      <div class="spark" data-a="${esc(t.article)}"></div>
      <div class="c-foot"><button class="more-btn" type="button" aria-expanded="false" aria-controls="d-${id}">${btnLabel()}</button>
        <span class="c-dates">${md(t.forecast[2].d)} гэхэд</span></div>
      <div class="detail" id="d-${id}" hidden>${detailHTML(t, ctx.src)}</div>
    </li>`;
  }
  const BIN = [[1.2, "--tm-0"], [2, "--tm-1"], [4, "--tm-2"], [10, "--tm-3"], [Infinity, "--tm-4"]];
  function tmKey(compact) {
    return `<div class="tm-key"><span>Хэмжээ = уншилт</span><span class="ramp" aria-hidden="true">${BIN.map((b) => `<i style="background:var(${b[1]})"></i>`).join("")}</span>
      <span>ердийнхөөс ×1 … ×10+</span><span><b aria-hidden="true">●</b> огцом өссөн</span>${compact ? "" : ""}</div>`;
  }
  function squarify(items, x, y, w, h) {
    const out = [], total = items.reduce((s, d) => s + d.v, 0);
    let rest = items.map((d) => ({ ...d, a: (d.v / total) * w * h }));
    while (rest.length) {
      const short = Math.min(w, h);
      let row = [rest[0]], worst = Infinity;
      for (let i = 1; i <= rest.length; i++) {
        const r = rest.slice(0, i), s = r.reduce((a, d) => a + d.a, 0);
        const mx = Math.max(...r.map((d) => d.a)), mn = Math.min(...r.map((d) => d.a));
        const wst = Math.max((short * short * mx) / (s * s), (s * s) / (short * short * mn));
        if (wst > worst) break;
        worst = wst; row = r;
      }
      const s = row.reduce((a, d) => a + d.a, 0), thick = s / short;
      let off = 0;
      row.forEach((d) => {
        const len = d.a / thick;
        out.push(w >= h ? { ...d, x, y: y + off, w: thick, h: len } : { ...d, x: x + off, y, w: len, h: thick });
        off += len;
      });
      if (w >= h) { x += thick; w -= thick; } else { y += thick; h -= thick; }
      rest = rest.slice(row.length);
    }
    return out;
  }
  function treemap(box, items, asof) {
    box.innerHTML = "";
    const W0 = box.clientWidth, H0 = box.clientHeight, small = H0 < 220;
    squarify(items.map((r) => ({ ...r, v: r.views })), 0, 0, W0, H0).forEach((r) => {
      const bin = BIN.find((b) => (r.ratio ?? 1) < b[0]), dark = bin[1] === "--tm-4";
      const a = document.createElement("a");
      a.className = "tm-cell" + (dark ? " dark" : "");
      a.href = href(r.article); a.dataset.a = r.article;
      Object.assign(a.style, { left: r.x + "px", top: r.y + "px", width: r.w + "px", height: r.h + "px", background: `var(${bin[1]})` });
      a.setAttribute("aria-label", `${r.title}: ${fmt(r.views)} уншилт, ердийнхөөс ×${r.ratio}${r.anomaly ? ", огцом өссөн" : ""}`);
      const fits = r.w > 68 && r.h > (small ? 22 : 34);
      a.innerHTML = (r.anomaly ? `<span class="tm-dot ${dark ? (O("tmdot") === "halo" ? "halo" : "inv") : ""}" aria-hidden="true"></span>` : "") +
        (fits ? `<span class="tm-t">${esc(r.title)}</span>` : "") + (fits && r.w > 90 && r.h > 54 ? `<span class="tm-v">${fmt(r.views)} · ×${r.ratio}</span>` : "");
      const tip = `<b>${esc(r.title)}</b><span>${fmt(r.views)} уншилт, ${longDate(asof)}</span><span>Ердийнхөөс ×${r.ratio}${r.anomaly ? " · ● огцом өссөн" : ""}</span>`;
      a.addEventListener("pointermove", (e) => { if (e.pointerType === "mouse") showTip(tip, e.clientX, e.clientY, { box, kind: "tm" }); });
      a.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") hideTip(); });
      a.addEventListener("focus", () => { const q = a.getBoundingClientRect(); showTip(tip, q.left + q.width / 2, q.top, { box, kind: "tm" }); });
      a.addEventListener("blur", hideTip);
      box.appendChild(a);
    });
  }
  function linkCardsAndCells() {
    const cells = [...main.querySelectorAll(".tm-cell")], cardOf = (a) => document.getElementById(slug(a));
    const cellOf = (a) => cells.find((c) => c.dataset.a === a);
    const hover = matchMedia("(hover: hover) and (pointer: fine)").matches;
    cells.forEach((c) => {
      if (hover) {
        c.addEventListener("mouseenter", () => cardOf(c.dataset.a)?.classList.add("lit"));
        c.addEventListener("mouseleave", () => cardOf(c.dataset.a)?.classList.remove("lit"));
      }
      c.addEventListener("click", (e) => {   // нэг tap = нэг үйлдэл (ADR 0027)
        const card = cardOf(c.dataset.a);
        if (O("tmtap") === "cond" && card) {
          e.preventDefault();
          card.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" });
          card.classList.remove("flash"); void card.offsetWidth; card.classList.add("flash");
        }
      });
    });
    main.querySelectorAll(".card").forEach((card) => {
      if (!hover) return;
      card.addEventListener("mouseenter", () => cellOf(card.dataset.a)?.classList.add("lit"));
      card.addEventListener("mouseleave", () => cellOf(card.dataset.a)?.classList.remove("lit"));
    });
    // Scroll-linked (ADR 0027): treemap харагдаж байхад дэлгэцийн голд байгаа карт нүдээ тодруулна
    const tm = main.querySelector(".tmap");
    if (!tm || !("IntersectionObserver" in window)) return;
    let tmVisible = false;
    new IntersectionObserver((es) => { tmVisible = es[0].isIntersecting; if (!tmVisible) cells.forEach((c) => c.classList.remove("lit")); }).observe(tm);
    const io = new IntersectionObserver((es) => {
      es.forEach((e) => {
        if (!tmVisible || hover) return;
        const cell = cellOf(e.target.dataset.a);
        if (cell) cell.classList.toggle("lit", e.isIntersecting);
      });
    }, { rootMargin: "-45% 0px -45% 0px" });
    main.querySelectorAll(".card").forEach((c) => io.observe(c));
  }
  function bindCards(ctx, items) {
    const byA = Object.fromEntries(items.map((t) => [t.article, t]));
    const draw = () => main.querySelectorAll(".spark[data-a]").forEach((b) => byA[b.dataset.a] && spark(b, byA[b.dataset.a]));
    draw(); redraws.push(draw);
    main.querySelectorAll(".more-btn").forEach((b) => b.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = b.getAttribute("aria-expanded") !== "true";
      if (O("expand") === "accordion") main.querySelectorAll('.more-btn[aria-expanded="true"]').forEach((o) => {
        o.setAttribute("aria-expanded", "false"); document.getElementById(o.getAttribute("aria-controls")).hidden = true; });
      b.setAttribute("aria-expanded", open); document.getElementById(b.getAttribute("aria-controls")).hidden = !open;
      App.measureSoon();
    }));
    // Stretched link: картын хоосон хэсэг дээр дарахад сэдвийн хуудас (товч, 3а-ээс бусад)
    if (O("link") === "stretch") main.querySelectorAll(".card.stretch").forEach((c) => c.addEventListener("click", (e) => {
      if (e.target.closest(".more-btn, .detail, a")) return;
      location.hash = href(c.dataset.a);
    }));
  }

  function skeleton(ms) {
    const start = Date.now();
    main.innerHTML = `<div class="sk sk-h" aria-hidden="true"></div><div class="sk sk-l" aria-hidden="true"></div>
      <div class="state-box" role="status"><p>Сервер унтаж байсан бол сэрэхэд хэсэг хугацаа шаардана. Хуудас өөрөө ачаалагдана.</p>
        <p class="code" id="sk-t">0 секунд болж байна</p></div>
      <ul class="cards" aria-hidden="true">${"<li class=\"sk sk-card\"></li>".repeat(4)}</ul>`;
    const tick = setInterval(() => { const n = document.getElementById("sk-t"); if (!n) return clearInterval(tick); n.textContent = `${Math.round((Date.now() - start) / 1000)} секунд болж байна`; }, 1000);
    return () => clearInterval(tick);
  }
  function errorBox(e, retry) {
    return `<div class="state-box" role="alert"><p><b>Өгөгдөл ирсэнгүй.</b> Сервер түр ажиллахгүй байж магадгүй.</p>
      <p><button class="btn" type="button" data-retry>Дахин оролдох</button></p>
      <p class="code">HTTP ${esc(e.status || e.message)} · ${esc(e.path || "")}</p></div>`;
  }
  function bindRetry(root, fn) {
    root.querySelectorAll("[data-retry]").forEach((b) => b.addEventListener("click", () => {
      if (S.retryOk) failLeft = 0;
      b.disabled = true; b.textContent = "Оролдож байна…";
      fn();
    }));
  }

  async function home() {
    const stop = Date.now() < coldUntil ? skeleton() : null;
    const [trR, mpR, srcR] = await Promise.allSettled([data("trending"), data("map"), data("track")]);
    stop && stop();
    if (trR.status === "rejected" && mpR.status === "rejected") {
      main.innerHTML = errorBox(trR.reason); bindRetry(main, home); return;
    }
    const d = trR.value || mpR.value, src = trackVer(srcR.value || (await getFile("track_record")));
    if (trR.status === "rejected") {   // хэсэгчилсэн алдаа: treemap ажилласаар
      const mp = mpR.value.map;
      meta(mp);
      main.innerHTML = `<h1 class="page-h">Огцом өссөн сэдвүүд</h1>${errorBox(trR.reason)}
        <section class="tm-sec"><h2 class="sec-h">${md(mp.asof)}-нд англи Wikipedia-д юу уншигдав?</h2>${tmKey()}<div class="tmap" id="tmap"></div></section>`;
      bindRetry(main, home);
      const draw = () => treemap(document.getElementById("tmap"), mp.items, mp.asof); draw(); redraws.push(draw);
      return;
    }
    const tr = d.trending, mp = d.map, items = tr.items, T = tr.T, ctx = { asof: tr.asof, T, src };
    meta(tr);
    const an = items.filter((t) => t.anomaly && t.verdict);
    const cont = an.filter((t) => t.verdict === "continue").sort((a, b) => b.pct - a.pct || b.ratio - a.ratio);
    const fade = an.filter((t) => t.verdict === "fade").sort((a, b) => (b.ratio ?? 0) - (a.ratio ?? 0));
    const beyond = items.filter((t) => t.rank != null);
    const cyc = tr.cyclical_rise.map((a) => items.find((t) => t.article === a)).filter(Boolean);
    const day = md(tr.asof), n = an.length, quietDay = n === 0;
    const vc = src.by_verdict.find((v) => v.key === (tr.anomalies.all_fade ? "fade" : "continue"));
    const h1 = quietDay ? `${day}-нд огцом өссөн сэдэв гараагүй`
      : O("h1") === "one" ? `${day}-нд огцом өссөн ${n} сэдэв: ирэх 3 өдөрт үргэлжлэх үү, унтрах уу?` : `${day}-нд огцом өссөн ${n} сэдэв`;
    const lead = quietDay ? `<p class="lead">Сэдвүүд ердийн түвшиндээ уншигдсан.</p>` : O("h1") === "split" ? `<p class="lead">Ирэх 3 өдөрт үргэлжлэх үү, унтрах уу?</p>` : "";
    const sum = quietDay ? "" : tr.anomalies.all_fade
      ? `<p class="sum">${n} сэдвийн бүгд нь ирэх 3 өдөрт унтрах төлөвтэй.</p>`
      : `<p class="sum"><b>${cont.length}</b> нь үргэлжлэх, <b>${fade.length}</b> нь унтрах төлөвтэй.</p>`;
    const trackLine = quietDay || !vc ? "" : `<p class="track-line"><span>Өмнө нь: model "${vc.label}" гэсэн ${vc.key === "continue" ? "сэдвийн" : ""} 10-аас ${tenths(vc.hit)} нь биелсэн (ердийн үед 10-аас ${tenths(vc.base_hit)})</span>
        <span class="prov">${esc(provText(src))}</span><a href="#/model">Хэр зөв байсан бэ? →</a></p>`;
    const layer1 = `<h1 class="page-h">${h1}</h1>${lead}${sum}
      ${quietDay ? "" : `<p class="neutral">Огцом уншилт сайн, муу гэсэн үг биш: нас баралт, дайн ч уншилтыг өсгөдөг.</p>`}${trackLine}`;
    const groups = quietDay ? "" : `${cont.length ? `<h2 class="grp-h">Үргэлжлэх төлөвтэй (${cont.length})</h2><ul class="cards">${cont.map((t) => cardHTML(t, ctx)).join("")}</ul>` : ""}
      ${fade.length ? `<h2 class="grp-h">Унтрах төлөвтэй (${fade.length})</h2><ul class="cards">${fade.map((t) => cardHTML(t, ctx)).join("")}</ul>` : ""}`;
    const dates = `${md(tr.items[0].forecast[0].d)}–${md(tr.items[0].forecast[2].d)}`;
    const beyondSec = `<section aria-labelledby="by-h"><h2 class="sec-h" id="by-h">${dates}-нд сэргэх төлөвтэй</h2>
      <p class="lead">Саяхан ердийн түвшнээсээ доош орсон, буцаж өсөх таамагтай сэдвүүд.</p>
      <p class="track-line"><span>Ийм таамгийн 10-аас 6 нь биелсэн (ердийн үед 10-аас 3)</span><span class="prov">сэргээж тооцсон · valid · model ${esc(src.model_version)}</span><a href="#/model">Хэр зөв байсан бэ? →</a></p>
      ${beyond.length ? `<ul class="cards">${beyond.map((t) => cardHTML(t, ctx)).join("")}</ul>` : `<p class="neutral">Энэ өдөр жагсаалтад сэдэв алга.</p>`}</section>`;
    const cycSec = `<details class="cyc-list"><summary>Долоо хоногийн хэвийн өсөлт (${cyc.length})</summary><div>
      <p class="neutral">Эдгээр нь гарагийн ердийн хэв маягаар өсөх таамагтай: ховор дохио биш.</p>
      ${cyc.length ? `<ul class="rowlist">${cyc.map((t) => `<li><a href="${href(t.article)}">${esc(t.title)}</a><span>${fcHTML(t, T)}</span></li>`).join("")}</ul>` : `<p class="neutral">Энэ өдөр алга.</p>`}</div></details>`;
    const tmTitle = `${day}-нд англи Wikipedia-д юу уншигдав?`;
    const tmSec = (low) => `<section class="tm-sec${low ? " low" : ""}" aria-labelledby="tm-h"><h2 class="${low ? "" : "sec-h"}" id="tm-h">${low ? "Бүх уншилтын дунд" : tmTitle}</h2>${tmKey(low)}<div class="tmap" id="tmap"></div></section>`;
    const catsSec = O("cats") === "on" ? catsHTML(items, ctx) : "";
    let body;
    if (S.v === "a") body = `${layer1}${groups}${quietDay ? "" : beyondSec}${quietDay ? beyondSec : ""}${cycSec}${tmSec(false)}${catsSec}`;
    else body = `${layer1}${quietDay ? `${beyondSec}<div class="g-wrap">${tmSec(true)}<div></div></div>` : `<div class="g-wrap">${tmSec(true)}<div>${groups}</div></div>${beyondSec}`}${cycSec}${catsSec}`;
    main.innerHTML = body;
    bindCards(ctx, items);
    const draw = () => { treemap(document.getElementById("tmap"), mp.items, mp.asof); linkCardsAndCells(); };
    draw(); redraws.push(draw);
  }
  function catsHTML(items, ctx) {
    const cats = {};
    [...items].sort((a, b) => b.views - a.views).forEach((t) => { (cats[t.category] ||= []).length < 4 && cats[t.category].push(t); });
    return `<section><h2 class="sec-h">Ангилал бүрт юу уншигдав?</h2><div class="cats">${Object.entries(cats).map(([k, ts]) => `
      <div class="cat"><h3>${esc(k)}</h3><ul class="rowlist">${ts.map((t) => `<li><a href="${href(t.article)}">${esc(t.title)}</a><span>${markHTML(t, ctx.asof) || ""}</span></li>`).join("")}</ul></div>`).join("")}</div></section>`;
  }

  // ═════════ Сэдвийн хуудас (3б) ═════════
  let tview = { days: 60, rp: null };
  function mainChart(box, t, src) {
    const days = O("range") === "off" ? 60 : tview.days;
    const hist = t.history.slice(-days), fc = t.forecast, H = hist.length, N = H + 3;
    const rp = days === 60 && tview.rp ? t.replay.find((r) => r.asof === tview.rp) : null;
    const narrow = box.clientWidth < 600, bars = O("mainmark") === "bars" && !(days === 180 && narrow);
    const label = `${t.title}: сүүлийн ${days} өдрийн уншилт ба ирэх 3 өдрийн таамаг. ${md(hist[H - 1].d)}-нд ${fmt(hist[H - 1].v)}, ${md(fc[2].d)}-нд ≈ ${fmt(fc[2].y)} (80%: ${fmt(fc[2].lo)}–${fmt(fc[2].hi)}).`;
    const { s, w, h } = svg(box, label);
    const pad = { l: 58, r: 12, t: 14, b: 24 }, step = (w - pad.l - pad.r) / N;
    const X = (i) => pad.l + (i + 0.5) * step;
    const max = niceMax(Math.max(...hist.map((d) => d.v), ...fc.map((f) => f.hi), ...(rp ? rp.forecast.map((f) => f.hi) : [])) * 1.04);
    const Y = (v) => h - pad.b - (v / max) * (h - pad.t - pad.b);
    for (let k = 0; k <= 4; k++) {
      const v = (max / 4) * k;
      el("line", { class: k ? "grid" : "axis", x1: pad.l, x2: w - pad.r, y1: Y(v), y2: Y(v) }, s);
      el("text", { class: "tick", x: pad.l - 6, y: Y(v) + 4, "text-anchor": "end" }, s).textContent = k ? fmt(v).replace(" мянга", " мян.") : "0";
    }
    if (O("base") === "on") {   // суурь цонх t−59…t−7 (ADR 0017)
      const a = Math.max(0, H - 1 - 59), b = H - 1 - 7;
      if (b > a) el("rect", { class: "basewin", x: X(a) - step / 2, y: pad.t, width: X(b) - X(a) + step, height: h - pad.t - pad.b }, s);
    }
    if (O("split") === "bg") el("rect", { class: "fc-bg", x: X(H) - step / 2, y: pad.t, width: 3 * step, height: h - pad.t - pad.b }, s);
    const xs = days === 60 ? 10 : 30;
    hist.forEach((d, i) => { if (i < H - 1 && (H - 1 - i) % xs === 0) el("text", { class: "tick", x: X(i), y: h - 6, "text-anchor": "middle" }, s).textContent = md(d.d); });
    el("text", { class: "tick", x: X(H + 2), y: h - 6, "text-anchor": "end" }, s).textContent = md(fc[2].d);
    const last = [X(H - 1), Y(hist[H - 1].v)];
    if (bars) {
      const bw = Math.max(1, step * 0.72);
      hist.forEach((d, i) => el("rect", { class: "bar", x: X(i) - bw / 2, y: Y(d.v), width: bw, height: Y(0) - Y(d.v), rx: Math.min(2, bw / 3) }, s));
      fc.forEach((f, i) => {
        el("rect", { class: "band", x: X(H + i) - step / 2 + 1, y: Y(f.hi), width: step - 2, height: Y(f.lo) - Y(f.hi) }, s);
        el("rect", { class: "bar-fc", x: X(H + i) - bw / 2, y: Y(f.y), width: bw, height: Y(0) - Y(f.y), rx: Math.min(2, bw / 3) }, s);
      });
    } else {
      const area = O("mainmark") === "line" || O("area180") === "area";
      if (area) el("path", { class: "act-area", d: poly([[X(0), Y(0)], ...hist.map((d, i) => [X(i), Y(d.v)]), [X(H - 1), Y(0)]]) + "Z" }, s);
      el("path", { class: "band", d: poly([last, ...fc.map((f, i) => [X(H + i), Y(f.hi)]), ...fc.map((f, i) => [X(H + i), Y(f.lo)]).reverse()]) + "Z" }, s);
      el("path", { class: "act", d: poly(hist.map((d, i) => [X(i), Y(d.v)])) }, s);
      el("path", { class: "fc", d: poly([last, ...fc.map((f, i) => [X(H + i), Y(f.y)])]) }, s);
    }
    if (t.normal != null) {
      el("line", { class: "norm", x1: pad.l, x2: X(H - 1), y1: Y(t.normal), y2: Y(t.normal) }, s);
      el("text", { class: "lbl", x: pad.l + 4, y: Y(t.normal) - 5 }, s).textContent = `ердийн өдөр ≈ ${fmt(t.normal)}`;
    }
    if (O("split") === "line") el("line", { class: "split", x1: X(H - 1) + step / 2, x2: X(H - 1) + step / 2, y1: pad.t, y2: h - pad.b }, s);
    // Replay: тэр өдрийн таамаг = дүүргэлтгүй mark + band outline (ADR 0026). Цэгтэй шугам биш.
    let rpTick = false;
    if (rp) {
      const iD = hist.findIndex((d) => d.d === rp.asof);
      if (iD >= 0) {
        const at = (k) => iD + 1 + k;
        if (bars) rp.forecast.forEach((f, k) => el("rect", { class: "rp-band", x: X(at(k)) - step / 2 + 1, y: Y(f.hi), width: step - 2, height: Y(f.lo) - Y(f.hi) }, s));
        else el("path", { class: "rp-band", d: poly([[X(iD), Y(hist[iD].v)], ...rp.forecast.map((f, k) => [X(at(k)), Y(f.hi)]), ...rp.forecast.map((f, k) => [X(at(k)), Y(f.lo)]).reverse()]) + "Z" }, s);
        if (bars) {
          const bw = Math.max(2, step * 0.72);
          rp.forecast.forEach((f, k) => {
            if (O("replaybar") === "tick") { rpTick = true; el("line", { class: "rp-tick", x1: X(at(k)) - bw / 2 - 2, x2: X(at(k)) + bw / 2 + 2, y1: Y(f.y), y2: Y(f.y) }, s); }
            else el("rect", { class: "rp-bar", x: X(at(k)) - bw / 2, y: Y(f.y), width: bw, height: Y(0) - Y(f.y) }, s);
          });
        } else el("path", { class: "rp-fc", d: poly([[X(iD), Y(hist[iD].v)], ...rp.forecast.map((f, k) => [X(at(k)), Y(f.y)])]) }, s);
      }
    }
    // Мөчлөг: зөвхөн h3, нимгэн тасралтгүй. Хэвтээ tick нэг л утгатай: replay tick байвал шошго болно (ADR 0026)
    let cm = O("cyclemark");
    if (cm === "tick" && rpTick) cm = "label";
    if (t.cyclical && cm !== "none" && t.cycle != null) {
      const yc = Y(hist[H - 1].v * (1 + t.cycle));
      if (cm === "tick") el("line", { class: "cyc-tick", x1: X(H + 2) - step * 0.6, x2: X(H + 2) + step * 0.6, y1: yc, y2: yc }, s);
      el("text", { class: "lbl", x: X(H + 2) - (cm === "tick" ? step : 0), y: yc - 6, "text-anchor": "end" }, s).textContent =
        cm === "tick" ? "долоо хоног бүр" : `долоо хоног бүр: ${pctText(t.cycle)}`;
    }
    const an = Object.fromEntries((t.anom || []).map((a) => [a.d, a.r]));
    hist.forEach((d, i) => { if (d.d in an) el("circle", { class: "dot", cx: X(i), cy: Y(d.v), r: days === 60 ? 3.5 : 2.5 }, s); });
    // Crosshair: tap / hover / гар (← →). Босоо чирэлт = гүйлгэх (touch-action: pan-y)
    const xh = el("line", { class: "xh", y1: pad.t, y2: h - pad.b, visibility: "hidden" }, s);
    const hp = el("circle", { class: "hp", r: 4.5, visibility: "hidden" }, s);
    const hit = el("rect", { class: "hit", x: pad.l, y: 0, width: w - pad.l - pad.r, height: h, tabindex: 0, "aria-label": "Өдөр сонгох: сум товчоор" }, s);
    let cur = -1;
    const owner = { box, kind: "main", clear: () => { xh.setAttribute("visibility", "hidden"); hp.setAttribute("visibility", "hidden"); cur = -1; } };
    function at(i, cx, cy) {
      cur = i = Math.max(0, Math.min(N - 1, i));
      const isF = i >= H, f = isF ? fc[i - H] : null, dd = isF ? f.d : hist[i].d, v = isF ? f.y : hist[i].v;
      xh.setAttribute("x1", X(i)); xh.setAttribute("x2", X(i)); xh.setAttribute("visibility", "visible");
      hp.setAttribute("cx", X(i)); hp.setAttribute("cy", Y(v)); hp.setAttribute("visibility", "visible");
      let html = isF ? `<b>≈ ${fmt(f.y)} уншилт (таамаг)</b><span>${longDate(dd, t.asof)}</span><span>80% магадлалтай: ${fmt(f.lo)} – ${fmt(f.hi)} хооронд</span>`
        : `<b>${fmt(v)} уншилт</b><span>${longDate(dd, t.asof)}</span>`;
      if (!isF && dd in an) html += `<span>● огцом өссөн: ердийнхөөс ×${an[dd]}</span>`;
      if (rp) { const k = rp.forecast.findIndex((x) => x.d === dd); if (k >= 0) html += `<span>${md(rp.asof)}-ны таамаг: ≈ ${fmt(rp.forecast[k].y)} (80%: ${fmt(rp.forecast[k].lo)}–${fmt(rp.forecast[k].hi)})</span><span>сэргээж тооцсон: тухайн өдөр хэрэглэгчид харагдаагүй</span>`; }
      if (!isF && O("base") === "on" && i >= Math.max(0, H - 60) && i <= H - 8) html += `<span>Ердийн түвшинг энэ хугацаагаар тооцсон (сүүлийн 7 хоног ороогүй)</span>`;
      const r = box.getBoundingClientRect();
      showTip(html, cx ?? r.left + X(i), cy ?? r.top + Y(v), owner);
    }
    const idx = (e) => Math.round((e.clientX - box.getBoundingClientRect().left - pad.l) / step - 0.5);
    hit.addEventListener("pointermove", (e) => { if (e.pointerType === "mouse") at(idx(e), e.clientX, e.clientY); });
    hit.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") hideTip(); });
    hit.addEventListener("click", (e) => at(idx(e), e.clientX, e.clientY));
    hit.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); at((cur < 0 ? H - 1 : cur) + (e.key === "ArrowLeft" ? -1 : 1)); }
    });
    hit.addEventListener("focus", () => at(H - 1));
    hit.addEventListener("blur", hideTip);
    App.meas.topic = { days, mark: bars ? "bars" : "line", band_h3_px: +(Y(fc[2].lo) - Y(fc[2].hi)).toFixed(1),
      peak_over_last: +(Math.max(...hist.map((d) => d.v)) / hist[H - 1].v).toFixed(1), chart_w: Math.round(w) };
  }
  const bandOutcome = (src, p) => {   // replay-ийн хажууд нэгдсэн track record (ADR 0020): таамгийн зурвасаар
    const key = p <= -0.2 ? "le_-20" : p <= -0.1 ? "-20_-10" : p < 0.1 ? "pm10" : p < 0.25 ? "10_25" : "ge_25";
    const b = src.by_band.find((x) => x.key === key);
    if (!b) return "";
    const [v, what] = key.startsWith("le") || key.startsWith("-20") ? [b.down10, "≥ 10% буурсан"] : key === "pm10" ? [1 - b.up10 - b.down10, "±10%-ийн дотор үлдсэн"] : [b.up10, "≥ 10% өссөн"];
    return `<div class="ia">${iaHTML(v, `Энэ зурвасын (${b.label}) бүх таамгийн <b>10-аас ${tenths(v)}</b> нь 3 өдрийн дараа ${what}`)}</div>
      <p class="prov">${esc(provText(src))} · n ${b.n.toLocaleString("en").replace(/,/g, " ")}</p>`;
  };
  async function topic(article) {
    const stop = Date.now() < coldUntil ? skeleton() : null;
    let d, src;
    try { [d, src] = await Promise.all([data("topic"), data("track")]); } catch (e) { stop && stop(); main.innerHTML = errorBox(e); bindRetry(main, () => topic(article)); return; }
    stop && stop();
    src = trackVer(src);
    const t = d.topics[article], tr = d.trending;
    meta(tr);
    if (!t) {
      main.innerHTML = `<a class="back" href="#/">← Нүүр</a><h1 class="topic-h">${esc(article.replace(/_/g, " "))}</h1>
        <p class="lead">Энэ сэдэв prototype-ийн fixture-д ороогүй (зөвхөн Anomaly, жагсаалт, treemap ба өсөлт/бууралтын эхний сэдвүүд).</p>`;
      return;
    }
    tview = { days: 60, rp: null };
    const T = tr.T, f3 = t.forecast[2];
    main.innerHTML = `<a class="back" href="#/">← Нүүр</a>
      <h1 class="topic-h">${esc(t.title)}</h1><p class="topic-cat">${esc(t.category)}</p>
      <p class="t-lines">${t.anomaly ? `${markHTML(t, tr.asof)}<span>${md(tr.asof)}-нд</span>` : `<span>${md(tr.asof)}-нд ${fmt(t.views)} уншилт (ердийн өдөр ≈ ${t.normal == null ? "—" : fmt(t.normal)})</span>`}</p>
      <p class="t-lines"><span>${t.verdict ? verdictHTML(t, T) : fcHTML(t, T)}</span><span>${md(f3.d)}-нд ≈ ${fmt(f3.y)} уншилт</span></p>
      <p class="t-lines" style="font-size:15px">80% магадлалтай: ${pctText(t.interval.lo)} … ${pctText(t.interval.hi)}</p>
      <div class="panel">
        <div class="ch-head"><p class="ch-title">Өдөр бүрийн уншилт <span class="prov" id="rp-prov" hidden>· ${esc(provText(src))}</span></p>
          ${O("range") === "on" ? `<div class="seg" role="group" aria-label="Хугацаа"><button type="button" data-days="60" aria-pressed="true">60 хоног</button><button type="button" data-days="180" aria-pressed="false">180 хоног</button></div>` : ""}</div>
        <div class="main-ch" id="main-ch"></div>
        <ul class="key">${O("mainmark") === "bars" ? `<li><i class="k-bar"></i>Бодит</li><li><i class="k-barfc"></i>Таамаг</li>` : `<li><i class="k-act"></i>Бодит</li><li><i class="k-fc"></i>Таамаг</li>`}
          <li><i class="k-band"></i>80% магадлалтай хүрээ</li><li><i class="k-dot"></i>Огцом өссөн өдөр</li><li><i class="k-norm"></i>Ердийн өдөр</li>
          ${O("base") === "on" ? `<li><i class="k-base"></i>Ердийн түвшний суурь (t−59…t−7)</li>` : ""}<li id="rp-key" hidden><i class="k-rp"></i>Өнгөрсөн таамаг</li></ul>
        <div class="replay"><h2 style="font-size:15px;margin:0 0 4px">Өнгөрсөн таамаг хэр зөв байсан бэ?</h2>
          <div class="rp-ctl"><label class="vh" for="rp-sel">Өдөр</label>
            <select id="rp-sel"><option value="">Өдөр сонгох…</option>${t.replay.map((r) => `<option value="${r.asof}">${md(r.asof)}-ны таамаг (${md(r.forecast[2].d)} хүртэл)</option>`).join("")}</select>
            <button class="btn ghost" type="button" id="rp-prev" aria-label="Өмнөх өдөр">←</button><button class="btn ghost" type="button" id="rp-next" aria-label="Дараагийн өдөр">→</button></div>
          <p class="rp-note" id="rp-note" hidden>Өнгөрсөн таамгийг 60 хоногийн горимд харна. Өдөр сонговол 60 горим руу шилжинэ.</p>
          <div class="rp-out" id="rp-out"></div></div>
        <details class="tbl"><summary>Хүснэгтээр харах</summary><div class="tbl-wrap"><table class="data"><caption class="vh">Сүүлийн 14 өдрийн уншилт ба ирэх 3 өдрийн таамаг</caption>
          <thead><tr><th>Өдөр</th><th>Бодит</th><th>Таамаг</th><th>80% доод</th><th>80% дээд</th><th>Огцом</th></tr></thead><tbody>
          ${t.history.slice(-14).map((h) => `<tr><td>${md(h.d)}</td><td>${fmt(h.v)}</td><td></td><td></td><td></td><td>${(t.anom || []).find((a) => a.d === h.d) ? "● ×" + t.anom.find((a) => a.d === h.d).r : ""}</td></tr>`).join("")}
          ${t.forecast.map((f) => `<tr><td>${md(f.d)}</td><td></td><td>${fmt(f.y)}</td><td>${fmt(f.lo)}</td><td>${fmt(f.hi)}</td><td></td></tr>`).join("")}</tbody></table></div></details>
      </div>
      <div class="panel"><h2 style="font-size:16px;margin:0 0 6px">${btnLabel()}</h2><div class="detail" style="border:0;padding-top:0">${detailHTML(t, src)}</div></div>`;
    const box = document.getElementById("main-ch");
    const draw = () => mainChart(box, t, src);
    draw(); redraws.push(draw);
    const sel = document.getElementById("rp-sel"), out = document.getElementById("rp-out");
    const setDays = (n) => {
      tview.days = n;
      main.querySelectorAll("[data-days]").forEach((b) => b.setAttribute("aria-pressed", +b.dataset.days === n));
      document.getElementById("rp-note").hidden = n === 60;
      document.getElementById("rp-prov").hidden = !(tview.rp && n === 60);
      document.getElementById("rp-key").hidden = !(tview.rp && n === 60);
      draw(); App.measureSoon();
    };
    main.querySelectorAll("[data-days]").forEach((b) => b.addEventListener("click", () => setDays(+b.dataset.days)));
    const setRp = (v) => {
      tview.rp = v || null; sel.value = v || "";
      const r = t.replay.find((x) => x.asof === v);
      if (r) {
        const f = r.forecast[2], act = t.history.find((h) => h.d === f.d);
        const where = !act ? "" : act.v < f.lo ? "80% хүрээнээс доогуур" : act.v > f.hi ? "80% хүрээнээс дээгүүр" : "80% хүрээн дотор";
        out.innerHTML = `<p><b>${md(r.asof)}-нд</b> ${md(f.d)}-ны уншилтыг ≈ ${fmt(f.y)} (80%: ${fmt(f.lo)}–${fmt(f.hi)}, ${arrowOf(r.pct)} ${pctText(r.pct)}) гэж таамагласан.
          ${act ? `Бодит нь <b>${fmt(act.v)}</b>: ${where}.` : ""}</p>${bandOutcome(src, r.pct)}<p class="rp-note">Нэг өдөр төлөөлөл биш: дээрх нь бүх ижил таамгийн дүн.</p>`;
      } else out.innerHTML = "";
      setDays(r ? 60 : tview.days);
    };
    sel.addEventListener("change", () => setRp(sel.value));
    const nav = (k) => { const ix = t.replay.findIndex((r) => r.asof === tview.rp); const n = ix < 0 ? 0 : Math.max(0, Math.min(t.replay.length - 1, ix + k)); setRp(t.replay[n].asof); };
    document.getElementById("rp-prev").addEventListener("click", () => nav(1));   // replay: шинээс хуучин руу эрэмбэлсэн
    document.getElementById("rp-next").addEventListener("click", () => nav(-1));
  }

  // ═════════ Бүх сэдэв (ADR 0013): Уншилтаар / Өсөлтөөр / Бууралтаар ═════════
  let lsort = "views", lall = false;
  async function list() {
    const stop = Date.now() < coldUntil ? skeleton() : null;
    let d;
    try { d = await data("trending"); } catch (e) { stop && stop(); main.innerHTML = errorBox(e); bindRetry(main, list); return; }
    stop && stop();
    const tr = d.trending, T = tr.T;
    meta(tr);
    const SORTS = [["views", "Уншилтаар"], ["up", "Өсөлтөөр"], ["down", "Бууралтаар"]];
    const items = [...tr.items].sort((a, b) => lsort === "views" ? b.views - a.views : lsort === "up" ? (b.pct ?? -9) - (a.pct ?? -9) : (a.pct ?? 9) - (b.pct ?? 9));
    const shown = lall ? items : items.slice(0, 40);
    main.innerHTML = `<h1 class="page-h">Бүх сэдэв</h1><p class="lead">${md(tr.asof)}-ний ${tr.items.length} сэдэв, ирэх 3 өдрийн (${tr.dates}) таамагтай.</p>
      <div class="sortbar"><span class="lbl" id="sort-l">Эрэмбэ:</span><div class="seg" role="group" aria-labelledby="sort-l">${SORTS.map(([k, n]) => `<button type="button" data-s="${k}" aria-pressed="${k === lsort}">${n}</button>`).join("")}</div></div>
      <ul class="lrows">${shown.map((t) => `<li class="lrow"><div><h3><a href="${href(t.article)}">${esc(t.title)}</a></h3>
        <p class="meta">${markHTML(t, tr.asof)}<span>${fmt(t.views)} уншилт</span>${t.measurable ? `<span>${fcHTML(t, T)}</span>` : `<span>цөөн уншилттай</span>`}</p></div>
        <div class="spark" data-a="${esc(t.article)}"></div></li>`).join("")}</ul>
      ${lall ? "" : `<p class="more-rows"><button class="btn ghost" type="button" id="all">Бүгдийг харах (${items.length})</button></p>`}`;
    main.querySelectorAll("[data-s]").forEach((b) => b.addEventListener("click", () => { lsort = b.dataset.s; list(); }));
    document.getElementById("all")?.addEventListener("click", () => { lall = true; list(); });
    const byA = Object.fromEntries(tr.items.map((t) => [t.article, t]));
    const draw = () => main.querySelectorAll(".spark[data-a]").forEach((b) => spark(b, byA[b.dataset.a]));
    draw(); redraws.push(draw);
  }

  // ═════════ Нотолгоо (#/model) ═════════
  async function proof() {
    const stop = Date.now() < coldUntil ? skeleton() : null;
    let src;
    try { src = trackVer(await data("track")); } catch (e) { stop && stop(); main.innerHTML = errorBox(e); bindRetry(main, proof); return; }
    stop && stop();
    const d = await getFile("normal"); meta(d.trending);
    const vc = (k) => src.by_verdict.find((v) => v.key === k), c = vc("continue"), f = vc("fade");
    const pc = (x) => `${(x * 100).toFixed(1)}%`, nn = (n) => n.toLocaleString("en").replace(/,/g, " ");
    main.innerHTML = `<h1 class="page-h">Таамаг өмнө нь хэр зөв байсан бэ?</h1>
      <p class="lead">Бүх тоо <b>сэргээж тооцсон</b>: ${src.from} … ${src.through}, ${src.days} өдөр, model ${esc(src.model_version)}. Тухайн өдөр хэрэглэгчид харагдсан (хадгалсан) таамгийн log хараахан хангалтгүй.</p>
      <div class="pf">
        <section class="pf-card"><h2>Огцом өссөн сэдэв "үргэлжлэх" гэсэн үед</h2>
          <div class="ia lg">${iaHTML(c.hit, `<b>10-аас ${tenths(c.hit)}</b> нь үнэхээр унтраагүй (${pc(c.hit)})`)}${iaHTML(c.base_hit, `10-аас ${tenths(c.base_hit)}: ердийн үед, бүх огцом өссөн сэдэв (${pc(c.base_hit)})`, true)}</div>
          <p class="prov">${esc(provText(src))} · n ${nn(c.n)}</p></section>
        <section class="pf-card"><h2>Огцом өссөн сэдэв "унтрах" гэсэн үед</h2>
          <div class="ia lg">${iaHTML(f.hit, `<b>10-аас ${tenths(f.hit)}</b> нь 3 өдрийн дараа ≥ 10% буурсан (${pc(f.hit)})`)}${iaHTML(f.base_hit, `10-аас ${tenths(f.base_hit)}: ердийн үед (${pc(f.base_hit)})`, true)}</div>
          <p>"Бүгд унтарна" гэсэн энгийн дүрэм ч ихэнхдээ зөв: model-ийн нэмэр нь цөөн "үргэлжлэх" таамагт.</p>
          <p class="prov">${esc(provText(src))} · n ${nn(f.n)}</p></section>
        <section class="pf-card wide"><h2>"Сэргэх төлөвтэй" жагсаалтад орсон үед</h2>
          <div class="ia lg">${iaHTML(0.589, `<b>10-аас 6</b> нь долоо хоногийн ердийнхөөс ≥ 10% илүү өссөн (58.9%)`)}${iaHTML(0.293, `10-аас 3: ердийн үед, бүх сэдэв (29.3%)`, true)}</div>
          <p>"Ердийн түвшин рүүгээ буцна" гэсэн энгийн дүрэм 10-аас 5 орчим (51.8%) байсан: жагсаалтын үнэ цэнийн ихэнх нь энэ энгийн баримтаас гардаг.</p>
          <p class="prov">сэргээж тооцсон · valid 2025 · model ${esc(src.model_version)} · docs/numbers/frequency.md</p></section>
        <section class="pf-card wide"><h2>Нөхцөл байдал бүрээр</h2><p>3 өдрийн дараах бодит үр дүн. Нөхцөл нь шалтгаан биш: ийм үед өмнө нь юу болж байсныг л харуулна.</p>
          <div class="tbl-wrap"><table class="data"><thead><tr><th>Нөхцөл</th><th>n</th><th>≥ +10% өссөн</th><th>≥ 10% буурсан</th><th>Илүүдэл ≥ +10%</th></tr></thead><tbody>
          <tr><td>Бүгд (ердийн үед)</td><td>${nn(src.base.n)}</td><td>${pc(src.base.up10)}</td><td>${pc(src.base.down10)}</td><td>${pc(src.base.excess10)}</td></tr>
          ${src.by_code.map((r) => `<tr><td>${esc(r.label)}</td><td>${nn(r.n)}</td><td>${pc(r.up10)}</td><td>${pc(r.down10)}</td><td>${pc(r.excess10)}</td></tr>`).join("")}</tbody></table></div></section>
        <section class="pf-card wide"><h2>Таамгийн зурвас бүрээр</h2>
          <div class="tbl-wrap"><table class="data"><thead><tr><th>Таамагласан (h3)</th><th>n</th><th>≥ +10% өссөн</th><th>≥ 10% буурсан</th></tr></thead><tbody>
          ${src.by_band.map((r) => `<tr><td>${esc(r.label)}</td><td>${nn(r.n)}</td><td>${pc(r.up10)}</td><td>${pc(r.down10)}</td></tr>`).join("")}</tbody></table></div></section>
        <section class="pf-card wide"><h2>Техникийн үнэлгээ</h2><p>Skill score, алгоритмын харьцуулалт, overfit: <a href="/#/model">одоогийн "Загвар" хуудас</a> (энэ prototype-д өөрчлөөгүй).</p></section>
      </div>`;
  }
  function facts() {
    main.innerHTML = `<h1 class="page-h">Хэв маяг</h1><p class="lead">Энэ хуудас 1-р шатанд хамаарахгүй. Одоогийнх: <a href="/#/facts">/#/facts</a>.</p>`;
  }

  // ═════════ Router ═════════
  let redraws = [], rt;
  addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { redraws.forEach((f) => f()); App.measureSoon(); }, 150); });
  function navHTML() {
    const page = (location.hash.replace(/^#\/?/, "").split("/")[0]) || "home";
    const L = [["#/", "home", "Нүүр"], ["#/list", "list", "Бүх сэдэв"], ["#/facts", "facts", "Хэв маяг"], ["#/model", "model", NAVNAME[O("navname")]]];
    document.getElementById("nav").innerHTML = L.map(([h, k, n]) => `<a href="${h}"${k === (page === "topic" ? "" : page) ? ' aria-current="page"' : ""}>${n}</a>`).join("");
    document.body.classList.toggle("tabbar", O("navlayout") === "tabbar");
  }
  async function route() {
    redraws = []; hideTip();
    navHTML();
    const [page, arg] = location.hash.replace(/^#\/?/, "").split("/");
    try {
      if (page === "topic") await topic(decodeURIComponent(arg || ""));
      else if (page === "list") await list();
      else if (page === "model") await proof();
      else if (page === "facts") facts();
      else await home();
    } catch (e) { main.innerHTML = errorBox(e); bindRetry(main, route); console.error(e); }
    if (page && page !== "home") main.focus({ preventScroll: true });
    App.measureSoon();
  }
  let lastHash = location.hash;
  addEventListener("hashchange", () => { const p = lastHash; lastHash = location.hash; route(); if (!location.hash.startsWith("#/topic") || !p.startsWith("#/topic")) scrollTo(0, 0); });

  // ═════════ Хэмжилт (variant panel-д харагдана, JSON-д орно) ═════════
  function measure() {
    const m = { viewport: `${innerWidth}×${innerHeight}`, page: location.hash || "#/" };
    m.h_overflow = document.documentElement.scrollWidth > document.documentElement.clientWidth;
    const navA = [...document.querySelectorAll("#nav a")];
    m.nav_rows = new Set(navA.map((a) => Math.round(a.getBoundingClientRect().top))).size;
    m.nav_min_h = Math.round(Math.min(...navA.map((a) => a.getBoundingClientRect().height)));
    const targets = [...document.querySelectorAll("#nav a, main button, main .c-name a, main .lrow h3 a, main summary, main select, .back")]
      .filter((e) => e.offsetParent !== null).map((e) => [e, e.getBoundingClientRect()]).filter(([, r]) => r.height < 44 || r.width < 24);
    m.small_targets = targets.length;
    m.small_targets_list = targets.slice(0, 6).map(([e, r]) => `${(e.textContent || "").trim().slice(0, 18)} ${Math.round(r.width)}×${Math.round(r.height)}`);
    const h1 = main.querySelector("h1");
    if (h1) m.h1_lines = Math.round(h1.getBoundingClientRect().height / parseFloat(getComputedStyle(h1).lineHeight));
    const cards = [...main.querySelectorAll(".card")];
    if (cards.length) {
      const fold = innerHeight - (O("navlayout") === "tabbar" && innerWidth <= 760 ? 57 : 0);
      m.cards_total = cards.length;
      m.cards_first_screen = cards.filter((c) => c.getBoundingClientRect().bottom + scrollY <= fold).length;
      m.first_card_top_px = Math.round(cards[0].getBoundingClientRect().top + scrollY);
      const bands = [...main.querySelectorAll(".card .spark")].map((s) => +s.dataset.bandPx).filter((x) => !isNaN(x)).sort((a, b) => a - b);
      if (bands.length) { m.spark_band_px_median = bands[bands.length >> 1]; m.spark_band_px_min = bands[0]; }
      const vs = [...main.querySelectorAll(".card .c-verdict")].filter((p) => p.querySelector(".cyc"));
      m.cycle_word_wraps = vs.filter((p) => p.getBoundingClientRect().height > parseFloat(getComputedStyle(p).lineHeight) * 1.5).length + " / " + vs.length;
    }
    const tm = main.querySelector(".tmap");
    if (tm) m.treemap_h = Math.round(tm.getBoundingClientRect().height);
    if (location.hash.startsWith("#/topic") && App.meas.topic) Object.assign(m, Object.fromEntries(Object.entries(App.meas.topic).map(([k, v]) => ["topic_" + k, v])));
    App.meas.last = m;
    return m;
  }
  let mt;
  const App = window.App = {
    GROUPS, DEF, VARIANTS, CASES, S, meas: {}, measure,
    measureSoon() { clearTimeout(mt); mt = setTimeout(() => { measure(); App.onMeasure && App.onMeasure(App.meas.last); }, 250); },
    set(k, v) { S.o[k] = v; toURL(); route(); },
    setVariant(v) { S.v = v; toURL(); route(); },
    setCase(c) { S.case = c; resetSim(); toURL(); route(); },
    setCold(n) { S.cold = n; resetSim(); toURL(); route(); },
    restartSim() { resetSim(); route(); },
    reset() { S.o = { ...DEF }; toURL(); route(); },
    start() { resetSim(); toURL(); route(); },
  };
})();
