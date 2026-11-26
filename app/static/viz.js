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

  // ═════════ Сэдвийн хуудасны гол график (3б, ADR 0026, 0027): шугам + area (бодит), тасархай + band (таамаг), ●, ердийн өдөр,
  // суурь цонх (t−59 … t−7) бүдэг дэвсгэр, түүх/таамгийн зааг. y 0-ээс, шугаман. rp = өнгөрсөн таамаг (зөвхөн 60 горимд). ═════════
  const niceMax = (m) => { const e = 10 ** Math.floor(Math.log10(m || 1)), f = m / e; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * e; };
  function mainChart(box, t, { days, rp }) {
    const T = W.TOPIC, hist = t.history.slice(-days), fc = t.forecast, H = hist.length, N = H + fc.length;
    if (!H) return;
    const { s, w, h } = svg(box, T.chartLabel(t, days, fmt));
    const pad = { l: 52, r: 12, t: 14, b: 24 }, step = (w - pad.l - pad.r) / N;
    const X = (i) => pad.l + (i + 0.5) * step;
    const max = niceMax(Math.max(...hist.map((d) => d.v), ...fc.map((f) => f.hi), ...(rp ? rp.forecast.map((f) => f.hi) : [])) * 1.04);
    const Y = (v) => h - pad.b - (v / max) * (h - pad.t - pad.b);
    for (let k = 0; k <= 4; k++) {
      const v = (max / 4) * k;
      el("line", { class: k ? "grid" : "axis", x1: pad.l, x2: w - pad.r, y1: Y(v), y2: Y(v) }, s);
      el("text", { class: "tick", x: pad.l - 6, y: Y(v) + 4, "text-anchor": "end" }, s).textContent = k ? fmt(v).replace(" мянга", " мян.") : "0";
    }
    const a0 = Math.max(0, H - 60), b0 = H - 8;   // суурь цонх t−59 … t−7 (ADR 0017)
    if (b0 > a0) el("rect", { class: "basewin", x: X(a0) - step / 2, y: pad.t, width: X(b0) - X(a0) + step, height: h - pad.t - pad.b }, s);
    const xs = days === 60 ? 10 : 30;
    hist.forEach((d, i) => { if (i < H - 4 && (H - 1 - i) % xs === 0) el("text", { class: "tick", x: X(i), y: h - 6, "text-anchor": "middle" }, s).textContent = W.md(d.d); });
    el("text", { class: "tick", x: X(N - 1), y: h - 6, "text-anchor": "end" }, s).textContent = W.md(fc[fc.length - 1].d);
    const last = [X(H - 1), Y(hist[H - 1].v)];
    el("path", { class: "act-area", d: poly([[X(0), Y(0)], ...hist.map((d, i) => [X(i), Y(d.v)]), [X(H - 1), Y(0)]]) + "Z" }, s);
    el("path", { class: "band", d: poly([last, ...fc.map((f, i) => [X(H + i), Y(f.hi)]), ...fc.map((f, i) => [X(H + i), Y(f.lo)]).reverse()]) + "Z" }, s);
    el("path", { class: "act", d: poly(hist.map((d, i) => [X(i), Y(d.v)])) }, s);
    el("path", { class: "fc", d: poly([last, ...fc.map((f, i) => [X(H + i), Y(f.y)])]) }, s);
    if (t.normal != null) {
      el("line", { class: "norm", x1: pad.l, x2: X(H - 1), y1: Y(t.normal), y2: Y(t.normal) }, s);
      el("text", { class: "lbl", x: pad.l + 4, y: Y(t.normal) - 5 }, s).textContent = T.norm(t.normal, fmt);
    }
    el("line", { class: "split", x1: X(H - 1) + step / 2, x2: X(H - 1) + step / 2, y1: pad.t, y2: h - pad.b }, s);
    if (rp) {   // өнгөрсөн таамаг = дүүргэлтгүй: бэх тасархай шугам + band-ийн outline (ADR 0026). Цэгтэй шугам биш (● = Anomaly)
      const iD = hist.findIndex((d) => d.d === rp.asof);
      if (iD >= 0) {
        const at = (k) => iD + 1 + k, o = [X(iD), Y(hist[iD].v)];
        el("path", { class: "rp-band", d: poly([o, ...rp.forecast.map((f, k) => [X(at(k)), Y(f.hi)]), ...rp.forecast.map((f, k) => [X(at(k)), Y(f.lo)]).reverse()]) + "Z" }, s);
        el("path", { class: "rp-fc", d: poly([o, ...rp.forecast.map((f, k) => [X(at(k)), Y(f.y)])]) }, s);
      }
    }
    const an = Object.fromEntries((t.anom || []).map((a) => [a.d, a.r]));
    hist.forEach((d, i) => { if (d.d in an) el("circle", { class: "dot", cx: X(i), cy: Y(d.v), r: days === 60 ? 3.5 : 2.5 }, s); });
    // Crosshair: tap / hover / гар (← →). Босоо чирэлт = гүйлгэх (touch-action: pan-y, ADR 0027)
    const xh = el("line", { class: "xh", y1: pad.t, y2: h - pad.b, visibility: "hidden" }, s);
    const hp = el("circle", { class: "hp", r: 4.5, visibility: "hidden" }, s);
    const hit = el("rect", { class: "hit", x: pad.l, y: 0, width: w - pad.l - pad.r, height: h, tabindex: 0, role: "slider",
      "aria-label": T.hitLabel, "aria-valuemin": 0, "aria-valuemax": N - 1, "aria-valuenow": H - 1 }, s);
    let cur = -1;
    const who = { box, kind: "main", clear: () => { xh.setAttribute("visibility", "hidden"); hp.setAttribute("visibility", "hidden"); cur = -1; } };
    function at(i, cx, cy) {
      cur = i = Math.max(0, Math.min(N - 1, i));
      const isF = i >= H, f = isF ? fc[i - H] : null, dd = isF ? f.d : hist[i].d, v = isF ? f.y : hist[i].v;
      xh.setAttribute("x1", X(i)); xh.setAttribute("x2", X(i)); xh.setAttribute("visibility", "visible");
      hp.setAttribute("cx", X(i)); hp.setAttribute("cy", Y(v)); hp.setAttribute("visibility", "visible");
      const lines = isF ? T.tipFc(f, t.asof, fmt) : T.tipActual(v, dd, t.asof, fmt);
      if (!isF && dd in an) lines.push(T.tipDot(an[dd]));
      if (rp) { const k = rp.forecast.findIndex((x) => x.d === dd); if (k >= 0) lines.push(...T.tipRp(rp.asof, rp.forecast[k], fmt)); }
      if (!isF && i >= a0 && i <= b0) lines.push(T.tipBase);
      hit.setAttribute("aria-valuenow", i); hit.setAttribute("aria-valuetext", lines.join(", "));
      const r = box.getBoundingClientRect();
      showTip(`<b>${esc(lines[0])}</b>${lines.slice(1).map((x) => `<span>${esc(x)}</span>`).join("")}`, cx ?? r.left + X(i), cy ?? r.top + Y(v), who);
    }
    const idx = (e) => Math.round((e.clientX - box.getBoundingClientRect().left - pad.l) / step - 0.5);
    hit.addEventListener("pointermove", (e) => { if (e.pointerType === "mouse") at(idx(e), e.clientX, e.clientY); });
    hit.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") hideTip(); });
    hit.addEventListener("click", (e) => at(idx(e), e.clientX, e.clientY));
    hit.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); at((cur < 0 ? H - 1 : cur) + (e.key === "ArrowLeft" ? -1 : 1)); }
    });
    hit.addEventListener("focus", () => at(H - 1));
    hit.addEventListener("blur", hideTip);
  }

  // ═════════ "Загвар" хуудасны графикууд (ADR 0027, 2026-11-26): өссөн = --data, буурсан / ердийн үед = саарал. Тоо бүр шууд шошготой,
  // tooltip-д яг тоо + n (data-tip: мөрүүдийг "\n"-ээр). Нэг хөдөлгөөн: багана суурийнхаа шугамаас ургана (.grow, reduced-motion үед үгүй). ═════════
  const tipAttr = (lines) => `data-tip="${esc(lines.join("\n"))}" tabindex="0"`;
  function bindTips(root) {
    root.querySelectorAll("[data-tip]").forEach((n) => {
      const show = (x, y) => { const [b, ...rest] = n.dataset.tip.split("\n"); showTip(`<b>${esc(b)}</b>${rest.map((r) => `<span>${esc(r)}</span>`).join("")}`, x, y, { box: n, kind: "proof" }); };
      const at = () => { const r = n.getBoundingClientRect(); show(r.left + Math.min(r.width / 2, 160), r.top); };
      n.addEventListener("pointermove", (e) => { if (e.pointerType === "mouse") show(e.clientX, e.clientY); });
      n.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") hideTip(); });
      n.addEventListener("click", at);
      n.addEventListener("focus", at);
      n.addEventListener("blur", hideTip);
    });
  }
  // Хэвтээ харьцуулалт: rows [{label, v (0…1), n, base}] → шошго дээр, багана доор, утга баганын үзүүрт
  const compare = (rows, big) => `<div class="cmp${big ? " big" : ""}">${rows.map((r) => `
    <div class="cmp-row${r.base ? " base" : ""}" ${tipAttr(W.PROOF.barTip(r.label, r.v, r.n))}>
      <span class="cmp-l">${esc(r.label)}</span>
      <span class="cmp-bar" style="--v:${r.v.toFixed(4)}"><i class="grow"></i><b>${esc(W.PROOF.pc(r.v))}</b></span>
    </div>`).join("")}</div>`;
  // Таамгийн зурвас бүрээр: өссөн (дээш, --data) ба буурсан (доош, саарал) хувь, зурвас зүүнээс баруун тийш өсөх дарааллаар = шат
  function stair(box, bands) {
    const P = W.PROOF.bands;
    const { s, w, h } = svg(box, `${P.q} ${bands.map((b) => `${b.label}: өссөн ${W.PROOF.pc(b.up10)}, буурсан ${W.PROOF.pc(b.down10)}`).join("; ")}`);
    const pad = { l: 8, r: 8, t: 22, b: 40 }, mid = pad.t + (h - pad.t - pad.b) / 2, half = (h - pad.t - pad.b) / 2;
    const col = (w - pad.l - pad.r) / bands.length, bw = Math.min(56, col * 0.56);
    el("line", { class: "axis", x1: pad.l, x2: w - pad.r, y1: mid, y2: mid }, s);
    bands.forEach((b, i) => {
      const cx = pad.l + col * (i + 0.5), up = b.up10 * half, dn = b.down10 * half;
      const g = el("g", { class: "st-col", tabindex: 0, "data-tip": W.PROOF.bands.tip(b).join("\n") }, s);
      el("rect", { class: "hitbox", x: cx - col / 2, y: pad.t - 18, width: col, height: h - pad.t - pad.b + 36 }, g);
      el("rect", { class: "st-up grow-y", x: cx - bw / 2, y: mid - up, width: bw, height: Math.max(up - 1, 0), rx: 3 }, g);
      el("rect", { class: "st-dn grow-y dn", x: cx - bw / 2, y: mid + 1, width: bw, height: Math.max(dn - 1, 0), rx: 3 }, g);
      el("text", { class: "val", x: cx, y: mid - up - 6, "text-anchor": "middle" }, g).textContent = W.PROOF.pc(b.up10);
      el("text", { class: "val2", x: cx, y: mid + dn + 14, "text-anchor": "middle" }, g).textContent = W.PROOF.pc(b.down10);
      el("text", { class: "tick", x: cx, y: h - 8, "text-anchor": "middle" }, g).textContent = b.label;
    });
    bindTips(box);
  }
  // Нөхцөл бүрээр хэвтээ diverging: буурсан ← | → өссөн, n < min_n бол бүдэг + "тоо хангалтгүй"
  const diverge = (codes) => `<div class="dv"><div class="dv-head" aria-hidden="true"><span></span><span>${esc(W.PROOF.codes.down)}</span><span>${esc(W.PROOF.codes.up)}</span></div>
    ${codes.map((c) => `<div class="dv-row${c.enough ? "" : " few"}" ${tipAttr(W.PROOF.codes.tip(c))}>
      <span class="dv-l">${esc(c.label)}${c.enough ? "" : ` <em>${esc(W.PROOF.codes.few)}</em>`}</span>
      <span class="dv-dn" style="--v:${c.down10.toFixed(4)}"><i class="grow rtl"></i><b>${esc(W.PROOF.pc(c.down10))}</b></span>
      <span class="dv-up" style="--v:${c.up10.toFixed(4)}"><i class="grow"></i><b>${esc(W.PROOF.pc(c.up10))}</b></span>
    </div>`).join("")}</div>`;
  // Нэг жишээ: D хүртэлх 14 өдөр + D+1…D+3-ын бодит (шугам) ба тэр өдрийн таамаг (тасархай + band)
  function replayMini(box, t, r) {
    const hist = t.history, iD = hist.findIndex((d) => d.d === r.asof);
    if (iD < 0) { box.innerHTML = ""; return; }
    const from = Math.max(0, iD - 13), seg = hist.slice(from, iD + 4), D = iD - from;
    const { s, w, h } = svg(box, W.PROOF.example.label(t.title, r));
    const pad = { l: 46, r: 10, t: 10, b: 22 }, N = seg.length;
    const X = (i) => pad.l + (i / (N - 1)) * (w - pad.l - pad.r);
    const max = niceMax(Math.max(...seg.map((d) => d.v), ...r.forecast.map((f) => f.hi)) * 1.04);
    const Y = (v) => h - pad.b - (v / max) * (h - pad.t - pad.b);
    [0, max / 2, max].forEach((v, k) => {
      el("line", { class: k ? "grid" : "axis", x1: pad.l, x2: w - pad.r, y1: Y(v), y2: Y(v) }, s);
      el("text", { class: "tick", x: pad.l - 6, y: Y(v) + 4, "text-anchor": "end" }, s).textContent = k ? fmt(v).replace(" мянга", " мян.") : "0";
    });
    const o = [X(D), Y(seg[D].v)];
    el("path", { class: "band", d: poly([o, ...r.forecast.map((f, k) => [X(D + 1 + k), Y(f.hi)]), ...r.forecast.map((f, k) => [X(D + 1 + k), Y(f.lo)]).reverse()]) + "Z" }, s);
    el("path", { class: "act", d: poly(seg.map((d, i) => [X(i), Y(d.v)])) }, s);
    el("path", { class: "fc", d: poly([o, ...r.forecast.map((f, k) => [X(D + 1 + k), Y(f.y)])]) }, s);
    el("line", { class: "split", x1: X(D), x2: X(D), y1: pad.t, y2: h - pad.b }, s);
    el("circle", { class: "hp", cx: o[0], cy: o[1], r: 4 }, s);
    el("text", { class: "tick", x: X(D), y: h - 6, "text-anchor": "middle" }, s).textContent = W.md(r.asof);
    el("text", { class: "tick", x: X(0), y: h - 6, "text-anchor": "start" }, s).textContent = W.md(seg[0].d);
    if (N - 1 > D) el("text", { class: "tick", x: X(N - 1), y: h - 6, "text-anchor": "end" }, s).textContent = W.md(seg[N - 1].d);
  }
  // Skill score + 95% интервал (h бүр): цэг = утга, зураас = интервал, 0-ээс
  function skillCI(box, skill) {
    const P = W.PROOF.skill, hs = [1, 2, 3].filter((k) => skill["h" + k]);
    const { s, w, h } = svg(box, `${P.q} ${hs.map((k) => `${k} өдөр: ${skill["h" + k].point}% (95%: ${skill["h" + k].lo}–${skill["h" + k].hi}%)`).join("; ")}`);
    const pad = { l: 110, r: 46, t: 6, b: 22 }, rowH = (h - pad.t - pad.b) / hs.length;
    const max = niceMax(Math.max(...hs.map((k) => skill["h" + k].hi)) * 1.1), X = (v) => pad.l + (v / max) * (w - pad.l - pad.r);
    [0, max / 2, max].forEach((v) => el("text", { class: "tick", x: X(v), y: h - 6, "text-anchor": "middle" }, s).textContent = `${Math.round(v)}%`);
    el("line", { class: "axis", x1: X(0), x2: X(0), y1: pad.t, y2: h - pad.b }, s);
    hs.forEach((k, i) => {
      const v = skill["h" + k], y = pad.t + rowH * (i + 0.5);
      const g = el("g", { class: "st-col", tabindex: 0, "data-tip": P.tip(k, v).join("\n") }, s);
      el("rect", { class: "hitbox", x: 0, y: y - rowH / 2, width: w, height: rowH }, g);
      el("text", { class: "lbl2", x: 0, y: y + 4 }, g).textContent = P.row(k);
      el("line", { class: "ci", x1: X(v.lo), x2: X(v.hi), y1: y, y2: y }, g);
      el("circle", { class: "ci-dot", cx: X(v.point), cy: y, r: 5 }, g);
      el("text", { class: "val", x: X(v.hi) + 8, y: y + 4 }, g).textContent = `${v.point}%`;
    });
    bindTips(box);
  }

  window.Viz = { el, svg, poly, showTip, hideTip, spark, treemap, tmKey, flash, linkHover, iconArray, reduced, mainChart, bindTips, compare, stair, diverge, replayMini, skillCI };
})();
