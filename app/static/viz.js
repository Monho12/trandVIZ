// W7 (#52) графикууд, theme 1 (ADR 0023, 0028): өгөгдөл нэг hue (--data бодит, --data-fc таамаг, --band итгэл), ● = бэх (--ink).
// Spark (давхарга 2), treemap (нүүрний дээд хэсэг), tooltip (tap / hover / focus, Esc ба гадна tap-аар хаагдана: WCAG 1.4.13).
// Огноо, үгийг өөрөө бичихгүй: Words (words.js). Тоо: Charts.fmt.
(function () {
  const W = window.Words, fmt = window.Charts.fmt, NS = "http://www.w3.org/2000/svg";
  const tipEl = document.getElementById("tip");
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

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
    return { s, w, h };
  }
  const poly = (pts) => pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("");

  // ═════════ Tooltip ═════════
  let owner = null;
  function showTip(html, x, y, who) {
    tipEl.innerHTML = html; tipEl.hidden = false; owner = who;
    const r = tipEl.getBoundingClientRect();
    let left = x + 14, top = y - r.height - 12;
    if (left + r.width > innerWidth - 8) left = x - r.width - 14;
    if (left < 8) left = 8;
    if (top < 8) top = y + 18;
    tipEl.style.left = left + "px"; tipEl.style.top = top + "px";
  }
  function hideTip() { tipEl.hidden = true; if (owner && owner.clear) owner.clear(); owner = null; }
  addEventListener("keydown", (e) => { if (e.key === "Escape") hideTip(); });
  document.addEventListener("pointerdown", (e) => { if (owner && !owner.box.contains(e.target)) hideTip(); });
  addEventListener("scroll", () => { if (owner && owner.kind === "cell") hideTip(); }, { passive: true });

  // ═════════ Spark: 14 өдөр + 3 өдрийн таамаг band-тай, ● = Anomaly өдөр. y 0-ээс, сэдэв бүр өөрийн масштаб (ADR 0027) ═════════
  function spark(box, t) {
    const hist = t.history.slice(-14), fc = t.forecast, H = hist.length;
    if (!H) return;
    const { s, w, h } = svg(box, W.sparkLabel(t, fmt));
    const pad = { l: 2, r: 4, t: 6, b: 4 }, N = H + fc.length;
    const max = Math.max(...hist.map((d) => d.v), ...fc.map((f) => f.hi)) * 1.05 || 1;
    const X = (i) => pad.l + (i / (N - 1)) * (w - pad.l - pad.r), Y = (v) => h - pad.b - (v / max) * (h - pad.t - pad.b);
    const last = [X(H - 1), Y(hist[H - 1].v)];
    el("path", { class: "band", d: poly([last, ...fc.map((f, i) => [X(H + i), Y(f.hi)]), ...fc.map((f, i) => [X(H + i), Y(f.lo)]).reverse()]) + "Z" }, s);
    el("path", { class: "act", d: poly(hist.map((d, i) => [X(i), Y(d.v)])) }, s);
    el("path", { class: "fc", d: poly([last, ...fc.map((f, i) => [X(H + i), Y(f.y)])]) }, s);
    el("line", { class: "split", x1: X(H - 1), x2: X(H - 1), y1: 2, y2: h }, s);
    const an = new Set((t.anom || []).map((a) => a.d));
    hist.forEach((d, i) => { if (an.has(d.d)) el("circle", { class: "dot", cx: X(i), cy: Y(d.v), r: 3.5 }, s); });
  }

  // ═════════ Treemap: хэмжээ = уншилт, өнгө = ×N (--data-ийн sequential scale), ● = огцом өссөн ═════════
  const BIN = [[1.2, "--tm-0"], [2, "--tm-1"], [4, "--tm-2"], [10, "--tm-3"], [Infinity, "--tm-4"]];
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
  const tmKey = () => `<div class="tm-key"><span>${esc(W.MAP_KEY.size)}</span><span class="ramp" aria-hidden="true">${BIN.map((b) => `<i style="background:var(${b[1]})"></i>`).join("")}</span>
    <span>${esc(W.MAP_KEY.ratio)}</span><span><b aria-hidden="true">●</b> ${esc(W.MAP_KEY.dot)}</span></div>`;
  // onCell(article, event): нүдэнд дарахад (нүүр: карт нь байвал карт руу, үгүй бол сэдвийн хуудас)
  function treemap(box, items, { asof, href, onCell }) {
    box.innerHTML = "";
    const W0 = box.clientWidth, H0 = box.clientHeight, small = H0 < 260;
    box.setAttribute("aria-label", W.mapTitle(asof));
    squarify(items.map((r) => ({ ...r, v: r.views })), 0, 0, W0, H0).forEach((r) => {
      const bin = BIN.find((b) => (r.ratio ?? 1) < b[0]), dark = bin[1] === "--tm-4";
      const a = document.createElement("a");
      a.className = "tm-cell" + (dark ? " dark" : "");
      a.href = href(r.article); a.dataset.a = r.article;
      Object.assign(a.style, { left: r.x + "px", top: r.y + "px", width: r.w + "px", height: r.h + "px", background: `var(${bin[1]})` });
      a.setAttribute("aria-label", W.cellLabel(r, fmt));
      const fits = r.w > 64 && r.h > (small ? 24 : 34);
      a.innerHTML = (r.anomaly ? `<span class="tm-dot${dark ? " halo" : ""}" aria-hidden="true"></span>` : "")
        + (fits ? `<span class="tm-t">${esc(r.title)}</span>` : "")
        + (fits && r.w > 90 && r.h > 54 ? `<span class="tm-v">${esc(W.cellValue(r, fmt))}</span>` : "");
      const [t1, t2, t3] = W.cellTip(r, asof, fmt);
      const tip = `<b>${esc(t1)}</b><span>${esc(t2)}</span><span>${esc(t3)}</span>`;
      const who = { box, kind: "cell" };
      a.addEventListener("pointermove", (e) => { if (e.pointerType === "mouse") showTip(tip, e.clientX, e.clientY, who); });
      a.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") hideTip(); });
      a.addEventListener("focus", () => { const q = a.getBoundingClientRect(); showTip(tip, q.left + q.width / 2, q.top, who); });
      a.addEventListener("blur", hideTip);
      if (onCell) a.addEventListener("click", (e) => onCell(r.article, e));
      box.appendChild(a);
    });
  }
  // Картыг тодруулах (treemap-ийн нүднээс ирэхэд): scroll + богино тодрол, reduced-motion үед хөдөлгөөнгүй
  function flash(card) {
    card.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" });
    card.classList.remove("flash"); void card.offsetWidth; card.classList.add("flash");
  }
  // Карт ↔ нүд hover (desktop): холбоотой нөгөөг нь тодруулна (ADR 0025, 0027)
  function linkHover(root) {
    if (!matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    const cells = [...root.querySelectorAll(".tm-cell")], cards = [...root.querySelectorAll(".card[data-a]")];
    const pair = (list, a) => list.find((x) => x.dataset.a === a);
    cells.forEach((c) => {
      c.addEventListener("mouseenter", () => pair(cards, c.dataset.a)?.classList.add("lit"));
      c.addEventListener("mouseleave", () => pair(cards, c.dataset.a)?.classList.remove("lit"));
    });
    cards.forEach((k) => {
      k.addEventListener("mouseenter", () => pair(cells, k.dataset.a)?.classList.add("lit"));
      k.addEventListener("mouseleave", () => pair(cells, k.dataset.a)?.classList.remove("lit"));
    });
  }

  // Icon array (ADR 0020): 10 нүд, k нь дүүрэн. base = "ердийн үед" (саарал)
  const iconArray = (rate, text, base) => {
    const n = Math.round(rate * 10);
    return `<span class="ia-sq${base ? " base" : ""}" aria-hidden="true">${Array.from({ length: 10 }, (_, i) => `<i class="${i < n ? "on" : ""}"></i>`).join("")}</span>
      <span class="ia-t">${text}</span>`;
  };

  window.Viz = { el, svg, poly, showTip, hideTip, spark, treemap, tmKey, flash, linkHover, iconArray, reduced };
})();
