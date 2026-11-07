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
  const MONTHS = ["1-р", "2-р", "3-р", "4-р", "5-р", "6-р", "7-р", "8-р", "9-р", "10-р", "11-р", "12-р"];
  const md = (s) => { const [, m, d] = s.split("-"); return `${+m}/${+d}`; };
  const longDate = (s) => { const [, m, d] = s.split("-"); return `${MONTHS[+m - 1]} сарын ${+d}`; };
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
  // Дээд талдаа 4px бөөрөнхий, доод тал нь суурь шугамд тулсан багана
  const colPath = (x, y, w, h) => {
    const r = Math.min(4, w / 2, h);
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  };
  function niceStep(max, count) {
    const raw = max / count, p = 10 ** Math.floor(Math.log10(raw)), f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  }
  function showTip(e, html) {
    tip.innerHTML = html; tip.hidden = false;
    const r = tip.getBoundingClientRect();
    let x = e.clientX + 14, y = e.clientY - r.height - 10;
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
    if (y < 8) y = e.clientY + 16;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  const hideTip = () => { tip.hidden = true; };

  /**
   * Баганан график: өдөр бүр нэг багана, тэгээс эхэлнэ.
   * Цэнхэр = бодит уншилт, улбар шар = таамаг; нимгэн шугам = таамгийн 80% бүс.
   */
  function columns(box, opts) {
    const { history, forecast = [], axis = false, label } = opts;
    const { svg, w, h } = svgFor(box, label);
    const pad = axis ? { l: 58, r: 6, t: 26, b: 24 } : { l: 0, r: 0, t: 2, b: 2 };
    const H = history.length, F = forecast.length, gapSlots = F ? 0.8 : 0;
    const slot = (w - pad.l - pad.r) / (H + F + gapSlots);
    const bw = Math.max(1, slot - (slot > 6 ? 2 : 1));     // баганын хооронд 2px зай
    const X = (i) => pad.l + (i + (i >= H ? gapSlots : 0)) * slot + (slot - bw) / 2;
    const max = Math.max(...history.map((p) => p.v), ...forecast.map((f) => f.hi)) || 1;
    const step = niceStep(max, axis ? 4 : 2), top = Math.ceil(max / step) * step;
    const base = h - pad.b, Y = (v) => base - (v / top) * (base - pad.t);

    if (axis) {
      for (let v = step; v <= top + 1e-9; v += step) {
        el("line", { class: "grid", x1: pad.l, x2: w - pad.r, y1: Y(v), y2: Y(v) }, svg);
        el("text", { class: "tick", x: pad.l - 8, y: Y(v) + 4, "text-anchor": "end" }, svg).textContent = fmt(v);
      }
      el("text", { class: "tick", x: pad.l - 8, y: base + 4, "text-anchor": "end" }, svg).textContent = "0";
    }
    const hl = el("rect", { class: "hl", y: pad.t, height: base - pad.t, width: slot, visibility: "hidden" }, svg);

    history.forEach((p, i) => {
      const b = el("path", { class: "bar b-blue", d: colPath(X(i), Y(p.v), bw, base - Y(p.v)) }, svg);
      b.style.setProperty("--i", i);
    });
    forecast.forEach((f, j) => {
      const i = H + j, x = X(i);
      const b = el("path", { class: "bar b-orange", d: colPath(x, Y(f.y), bw, base - Y(f.y)) }, svg);
      b.style.setProperty("--i", i);
      if (axis) el("line", { class: "range", x1: x + bw / 2, x2: x + bw / 2, y1: Y(f.hi), y2: Y(f.lo) }, svg);
    });
    el("line", { class: "base", x1: pad.l, x2: w - pad.r, y1: base, y2: base }, svg);

    if (axis) {
      // Бодит / таамаг хуваах шугам
      if (F) {
        const sx = pad.l + (H + gapSlots / 2) * slot;
        el("line", { class: "split", x1: sx, x2: sx, y1: pad.t - 14, y2: base }, svg);
        el("text", { class: "val2", x: sx - 6, y: pad.t - 6, "text-anchor": "end" }, svg).textContent = "← бодит";
        el("text", { class: "val2", x: sx + 6, y: pad.t - 6 }, svg).textContent = "таамаг →";
      }
      // Сонгомол шошго: өчигдрийн утга
      const lx = X(H - 1) + bw / 2, lv = history[H - 1].v;
      el("text", { class: "val", x: lx, y: Y(lv) - 6, "text-anchor": F ? "end" : "middle" }, svg).textContent = fmt(lv);
      // Огноо
      const every = Math.max(1, Math.round(H / 6));
      for (let i = 0; i < H - every / 2; i += every)
        el("text", { class: "tick", x: X(i) + bw / 2, y: h - 6, "text-anchor": "middle" }, svg).textContent = md(history[i].d);
      if (F) el("text", { class: "tick", x: X(H + F - 1) + bw / 2, y: h - 6, "text-anchor": "middle" }, svg).textContent = md(forecast[F - 1].d);
    }

    // Hover: багана бүрийн бүтэн өндрийн үл үзэгдэх талбай
    const hits = el("g", {}, svg);
    for (let i = 0; i < H + F; i++) {
      const r = el("rect", { x: X(i) - (slot - bw) / 2, y: 0, width: slot, height: h, fill: "transparent" }, hits);
      const isF = i >= H, d = isF ? forecast[i - H] : history[i];
      const html = isF
        ? `<b>${longDate(d.d)}, таамаг</b>≈ ${fmt(d.y)} уншилт<br><span>80% магадлалтай: ${fmt(d.lo)} – ${fmt(d.hi)}</span>`
        : `<b>${longDate(d.d)}</b>${fmt(d.v)} уншилт`;
      r.addEventListener("pointermove", (e) => { hl.setAttribute("x", X(i) - (slot - bw) / 2); hl.setAttribute("visibility", "visible"); showTip(e, html); });
      r.addEventListener("pointerleave", () => { hl.setAttribute("visibility", "hidden"); hideTip(); });
    }
  }

  /** Model-ийн алдааг энгийн аргуудтай харьцуулах бүлэглэсэн багана */
  function groups(box, rows, keys, names, label) {
    const { svg, w, h } = svgFor(box, label);
    const pad = { l: 4, r: 4, t: 18, b: 26 };
    const max = Math.max(...rows.flatMap((r) => keys.map((k) => r[k]))) * 1.1;
    const gw = (w - pad.l - pad.r) / rows.length, bw = Math.min(34, (gw - 28) / keys.length);
    const base = h - pad.b, cls = ["b-blue", "b-gray", "b-gray"];
    rows.forEach((r, i) => {
      const gx = pad.l + i * gw + (gw - bw * keys.length) / 2;
      keys.forEach((k, j) => {
        const bh = (r[k] / max) * (base - pad.t), x = gx + j * bw + 1;
        el("path", { class: cls[j], d: colPath(x, base - bh, bw - 2, bh), opacity: j === 2 ? 0.6 : 1 }, svg);
        el("text", { class: j === 0 ? "val" : "val2", x: x + (bw - 2) / 2, y: base - bh - 5, "text-anchor": "middle", "font-size": 11 }, svg).textContent = r[k].toFixed(2);
      });
      el("text", { class: "tick", x: pad.l + i * gw + gw / 2, y: h - 6, "text-anchor": "middle", "font-size": 12 }, svg).textContent = `${r.h} өдрийн дараа`;
    });
    el("line", { class: "base", x1: pad.l, x2: w - pad.r, y1: base, y2: base }, svg);
    void names;
  }

  /** Сургалтын муруй: сургалт ба validation алдаа */
  function curve(box, pts, best, label) {
    const { svg, w, h } = svgFor(box, label);
    const pad = { l: 40, r: 74, t: 18, b: 24 };
    const xs = pts.map((p) => p.it), ys = pts.flatMap((p) => [p.train, p.valid]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = 0, y1 = Math.max(...ys) * 1.05;
    const X = (v) => pad.l + ((v - x0) / (x1 - x0)) * (w - pad.l - pad.r);
    const Y = (v) => pad.t + (1 - (v - y0) / (y1 - y0)) * (h - pad.t - pad.b);
    const st = niceStep(y1, 4);
    for (let v = 0; v <= y1; v += st) {
      el("line", { class: v ? "grid" : "base", x1: pad.l, x2: w - pad.r, y1: Y(v), y2: Y(v) }, svg);
      el("text", { class: "tick", x: pad.l - 6, y: Y(v) + 4, "text-anchor": "end" }, svg).textContent = +v.toFixed(2);
    }
    [x0, Math.round((x0 + x1) / 2), x1].forEach((v) => el("text", { class: "tick", x: X(v), y: h - 6, "text-anchor": "middle" }, svg).textContent = v);
    el("line", { class: "stop", x1: X(best), x2: X(best), y1: pad.t - 8, y2: h - pad.b }, svg);
    el("text", { class: "val2", x: X(best) + 6, y: pad.t }, svg).textContent = `зогсоосон: ${best}`;
    el("path", { class: "l-gray", d: "M" + pts.map((p) => `${X(p.it)},${Y(p.train)}`).join(" L") }, svg);
    el("path", { class: "l-blue", d: "M" + pts.map((p) => `${X(p.it)},${Y(p.valid)}`).join(" L") }, svg);
    const last = pts[pts.length - 1];
    el("text", { class: "val", x: X(last.it) + 8, y: Y(last.valid) - 2 }, svg).textContent = "validation";
    el("text", { class: "val2", x: X(last.it) + 8, y: Y(last.train) + 12 }, svg).textContent = "сургалт";
  }

  /** Feature importance: хэвтээ багана */
  function hbars(box, rows, label) {
    const { svg, w, h } = svgFor(box, label);
    const lw = 128, max = Math.max(...rows.map((r) => r.gain)), rh = h / rows.length;
    rows.forEach((r, i) => {
      const y = i * rh, bw = (r.gain / max) * (w - lw - 46), bh = Math.min(16, rh * 0.6);
      el("text", { class: "tick", x: lw - 10, y: y + rh / 2 + 4, "text-anchor": "end", "font-size": 12 }, svg).textContent = r.f;
      el("rect", { class: i < 3 ? "b-blue" : "b-gray", x: lw, y: y + (rh - bh) / 2, width: bw, height: bh, rx: 3 }, svg);
      el("text", { class: "val2", x: lw + bw + 8, y: y + rh / 2 + 4 }, svg).textContent = r.gain + "%";
    });
  }

  window.Charts = { columns, groups, curve, hbars, fmt, longDate };
})();
