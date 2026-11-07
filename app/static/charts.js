// Хөнгөн SVG график — гадны сан ашиглахгүй (CPU, RAM бага).
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const tip = document.getElementById("tip");

  const fmt = (v) => {
    v = Math.round(v);
    if (v >= 1e6) return (v / 1e6).toFixed(v >= 1e7 ? 0 : 1).replace(/\.0$/, "") + " сая";
    if (v >= 1e3) return (v / 1e3).toFixed(v >= 1e4 ? 0 : 1).replace(/\.0$/, "") + " мянга";
    return String(v);
  };
  const longDate = (s) => { const [, m, d] = s.split("-"); return `${+m}-р сарын ${+d}`; };
  const el = (tag, attrs = {}, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  };
  function svgFor(box, label) {
    box.innerHTML = "";
    const w = Math.max(box.clientWidth, 120), h = Math.max(box.clientHeight, 24);
    const svg = el("svg", { class: "ch", viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": label || "" });
    box.appendChild(svg);
    return { svg, w, h };
  }
  // Дээд тал нь бөөрөнхий, доод тал нь суурь шугамд тулсан багана
  const colPath = (x, y, w, h) => {
    const r = Math.min(4, w / 2, h);
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  };
  function showTip(e, html) {
    tip.innerHTML = html; tip.hidden = false;
    const r = tip.getBoundingClientRect();
    let x = e.clientX + 14, y = e.clientY - r.height - 12;
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
    if (y < 8) y = e.clientY + 16;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  const hideTip = () => { tip.hidden = true; };

  /**
   * Түүх график: өдөр бүр нэг багана.
   * Анхаарлыг өчигдөр (тод цэнхэр) ба таамаг (улбар шар) руу чиглүүлнэ; бусад өдөр бүдэг.
   * Тасархай хэвтээ шугам = ердийн өдөр — "×N дахин" гэдгийг нүдээр харуулна.
   * Тэнхлэг, тор, legend байхгүй: гол утгуудыг шууд бичнэ.
   */
  function story(box, { history, forecast = [], normal, label }) {
    const { svg, w, h } = svgFor(box, label);
    const pad = { l: 0, r: 0, t: 44, b: 24 };
    const H = history.length, F = forecast.length, gap = F ? 0.9 : 0;
    const slot = (w - pad.l - pad.r) / (H + F + gap);
    const bw = Math.max(1, slot - (slot > 7 ? 3 : 1));
    const X = (i) => pad.l + (i + (i >= H ? gap : 0)) * slot + (slot - bw) / 2;
    const max = Math.max(...history.map((p) => p.v), ...forecast.map((f) => f.y), normal || 0) || 1;
    const base = h - pad.b, Y = (v) => base - (v / max) * (base - pad.t);
    const hl = el("rect", { class: "hl", y: 0, height: base, width: slot, rx: 4, visibility: "hidden" }, svg);

    history.forEach((p, i) => {
      const b = el("path", { class: "bar " + (i === H - 1 ? "b-now" : "b-past"), d: colPath(X(i), Y(p.v), bw, base - Y(p.v)) }, svg);
      b.style.setProperty("--i", i);
    });
    forecast.forEach((f, j) => {
      const b = el("path", { class: "bar b-cast", d: colPath(X(H + j), Y(f.y), bw, base - Y(f.y)) }, svg);
      b.style.setProperty("--i", H + j);
    });
    el("line", { class: "base", x1: 0, x2: w, y1: base, y2: base }, svg);

    // Ердийн өдрийн түвшин
    if (normal) {
      const ny = Y(normal), xEnd = X(H - 1) - 4;
      el("line", { class: "norm", x1: 0, x2: xEnd, y1: ny, y2: ny }, svg);
      el("text", { class: "t-norm", x: 0, y: ny - 6 }, svg).textContent = `ердийн өдөр ${fmt(normal)}`;
    }
    // Хоёрхон шошго: өчигдөр ба сүүлийн таамаг
    // Өчигдрийн шошго: зүүн тийш сунах тул доор нь орох баганануудаас дээгүүр байрлуулна
    const nx = X(H - 1) + bw, nv = history[H - 1].v;
    const nt = el("text", { class: "t-now", x: nx, y: 0, "text-anchor": "end" }, svg);
    nt.textContent = `өчигдөр ${fmt(nv)}`;
    const tw = nt.getComputedTextLength();
    let under = nv;
    history.forEach((p, i) => { if (X(i) + bw >= nx - tw) under = Math.max(under, p.v); });
    nt.setAttribute("y", Math.max(32, Y(under) - 8));
    if (F) {
      // Таамгийн шошго: доор нь орох бүх баганаас дээгүүр, өчигдрийн шошготой давхцахгүй
      const lf = forecast[F - 1], fx = X(H + F - 1) + bw;
      const ft = el("text", { class: "t-cast", x: fx, y: 0, "text-anchor": "end" }, svg);
      ft.textContent = `≈ ${fmt(lf.y)}`;
      const fw = ft.getComputedTextLength();
      let fu = lf.y;
      history.forEach((p, i) => { if (X(i) + bw >= fx - fw) fu = Math.max(fu, p.v); });
      forecast.forEach((f) => { fu = Math.max(fu, f.y); });
      let fy = Y(fu) - 8;
      if (fx - fw < nx && Math.abs(fy - +nt.getAttribute("y")) < 16) fy = +nt.getAttribute("y") - 18;
      ft.setAttribute("y", Math.max(13, fy));
    }
    // Огноо: зөвхөн эхний өдөр ба "ирэх 3 өдөр"
    el("text", { class: "t-date", x: X(0), y: h - 4 }, svg).textContent = longDate(history[0].d);
    if (F) el("text", { class: "t-date", x: X(H + F - 1) + bw, y: h - 4, "text-anchor": "end" }, svg).textContent = "ирэх 3 өдөр";

    // Hover: багана бүрийн бүтэн өндрийн үл үзэгдэх талбай
    const hits = el("g", {}, svg);
    for (let i = 0; i < H + F; i++) {
      const isF = i >= H, d = isF ? forecast[i - H] : history[i];
      const html = isF
        ? `<b>${longDate(d.d)} (таамаг)</b>≈ ${fmt(d.y)} уншилт<br><span>Ихэвчлэн ${fmt(d.lo)}–${fmt(d.hi)} хооронд</span>`
        : `<b>${longDate(d.d)}</b>${fmt(d.v)} уншилт`;
      const r = el("rect", { x: X(i) - (slot - bw) / 2, y: 0, width: slot, height: h, fill: "transparent" }, hits);
      r.addEventListener("pointermove", (e) => { hl.setAttribute("x", X(i) - (slot - bw) / 2); hl.setAttribute("visibility", "visible"); showTip(e, html); });
      r.addEventListener("pointerleave", () => { hl.setAttribute("visibility", "hidden"); hideTip(); });
    }
  }

  /** Model-ийн алдааг энгийн аргуудтай харьцуулах: model тод, бусад саарал */
  function compare(box, rows, label) {
    const { svg, w, h } = svgFor(box, label);
    const lw = Math.min(170, w * 0.36), rh = h / rows.length, max = Math.max(...rows.map((r) => r.v));
    rows.forEach((r, i) => {
      const y = i * rh, bh = Math.min(26, rh * 0.62), bw = (r.v / max) * (w - lw - 60);
      el("text", { class: i === 0 ? "t-val" : "t-val2", x: 0, y: y + rh / 2 + 4, "font-size": 14 }, svg).textContent = r.name;
      el("rect", { class: i === 0 ? "b-now" : "b-gray", x: lw, y: y + (rh - bh) / 2, width: bw, height: bh, rx: 4 }, svg);
      el("text", { class: i === 0 ? "t-val" : "t-val2", x: lw + bw + 8, y: y + rh / 2 + 4, "font-size": 14 }, svg).textContent = r.v.toFixed(2);
    });
  }

  /** Сургалтын муруй: сургалт ба validation алдаа, хоёрхон шугам */
  function curve(box, pts, best, label) {
    const { svg, w, h } = svgFor(box, label);
    const pad = { l: 0, r: 84, t: 22, b: 24 };
    const xs = pts.map((p) => p.it), ys = pts.flatMap((p) => [p.train, p.valid]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y1 = Math.max(...ys) * 1.05;
    const X = (v) => pad.l + ((v - x0) / (x1 - x0)) * (w - pad.l - pad.r);
    const Y = (v) => pad.t + (1 - v / y1) * (h - pad.t - pad.b);
    el("line", { class: "base", x1: 0, x2: w - pad.r, y1: Y(0), y2: Y(0) }, svg);
    el("line", { class: "stop", x1: X(best), x2: X(best), y1: pad.t - 10, y2: Y(0) }, svg);
    el("text", { class: "t-cast", x: X(best) + 6, y: pad.t - 2 }, svg).textContent = `${best}-д зогсоосон`;
    el("path", { class: "l-gray", d: "M" + pts.map((p) => `${X(p.it)},${Y(p.train)}`).join(" L") }, svg);
    el("path", { class: "l-blue", d: "M" + pts.map((p) => `${X(p.it)},${Y(p.valid)}`).join(" L") }, svg);
    const last = pts[pts.length - 1];
    el("text", { class: "t-val", x: X(last.it) + 8, y: Y(last.valid) - 2 }, svg).textContent = "шалгалт";
    el("text", { class: "t-val2", x: X(last.it) + 8, y: Y(last.train) + 14 }, svg).textContent = "сургалт";
    el("text", { class: "t-date", x: 0, y: h - 4 }, svg).textContent = "сургалтын давталт →";
  }

  /** Feature importance: эхний 3 нь тод, бусад нь саарал */
  function hbars(box, rows, label) {
    const { svg, w, h } = svgFor(box, label);
    const lw = Math.min(190, w * 0.4), max = Math.max(...rows.map((r) => r.gain)), rh = h / rows.length;
    rows.forEach((r, i) => {
      const y = i * rh, bw = (r.gain / max) * (w - lw - 44), bh = Math.min(14, rh * 0.6);
      el("text", { class: i < 3 ? "t-val" : "t-val2", x: 0, y: y + rh / 2 + 4, "font-size": 13 }, svg).textContent = r.name || r.f;
      el("rect", { class: i < 3 ? "b-now" : "b-gray", x: lw, y: y + (rh - bh) / 2, width: bw, height: bh, rx: 3 }, svg);
      el("text", { class: "t-val2", x: lw + bw + 8, y: y + rh / 2 + 4 }, svg).textContent = r.gain + "%";
    });
  }

  window.Charts = { story, compare, curve, hbars, fmt, longDate };
})();
