// Хөнгөн SVG график — гадны сан ашиглахгүй (CPU, RAM бага).
(function () {
  const NS = "http://www.w3.org/2000/svg";

  const fmt = (v) => {
    if (v >= 1e6) return (v / 1e6).toFixed(v >= 1e7 ? 0 : 1).replace(/\.0$/, "") + " сая";
    if (v >= 1e3) return (v / 1e3).toFixed(v >= 1e4 ? 0 : 1).replace(/\.0$/, "") + " мянга";
    return String(Math.round(v));
  };
  const md = (s) => { const [, m, d] = s.split("-"); return `${+m}/${+d}`; };
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

  /**
   * Дууны долгион шиг график: өдөр бүр = төвөөс дээш доош тусгалтай багана.
   * Өндөр нь log хуваарьтай хандалт. Хэвийнээсээ 3+ дахин чанга өдрүүд улаан.
   * Таамаг = бүдэг ягаан "сүүдэр" багана (доод–дээд хязгаар) + дотор нь таамгийн утга.
   */
  function wave(box, opts) {
    const { history, forecast = [], axis = false, label } = opts;
    const { svg, w, h } = svgFor(box, label);
    const pad = { l: 0, r: 0, t: axis ? 18 : 2, b: axis ? 22 : 2 };
    const n = history.length + forecast.length;
    const ly = (v) => Math.log10(Math.max(v, 1));
    const vals = history.map((p) => ly(p.v)).concat(forecast.flatMap((f) => [ly(f.lo), ly(f.hi)]));
    const top = Math.max(...vals), bot = Math.min(...vals) - 0.25;
    const mid = pad.t + (h - pad.t - pad.b) / 2, half = (h - pad.t - pad.b) / 2;
    const A = (v) => Math.max(1.2, ((ly(v) - bot) / (top - bot)) * half); // хагас өндөр
    const slot = (w - pad.l - pad.r) / n, bw = Math.max(1, slot * (n > 90 ? 0.7 : 0.42));
    const X = (i) => pad.l + i * slot + (slot - bw) / 2;

    const sorted = history.map((p) => p.v).sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)] || 1;

    el("line", { class: "mid", x1: 0, x2: w, y1: mid, y2: mid }, svg);
    history.forEach((p, i) => {
      const a = A(p.v);
      const r = el("rect", { class: "sig" + (p.v >= 3 * median ? " red" : ""), x: X(i), y: mid - a, width: bw, height: 2 * a, rx: Math.min(bw / 2, 1.5) }, svg);
      r.style.setProperty("--i", i);
    });
    forecast.forEach((f, j) => {
      const i = history.length + j, hi = A(f.hi), lo = A(f.lo), y = A(f.y);
      el("rect", { class: "ghost", x: X(i), y: mid - hi, width: bw, height: 2 * hi, rx: 1.5 }, svg);
      el("rect", { class: "ghostcore", x: X(i) + bw * 0.3, y: mid - y, width: bw * 0.4, height: 2 * y }, svg);
      void lo;
    });
    if (forecast.length) {
      const xn = pad.l + history.length * slot;
      el("line", { class: "now", x1: xn, x2: xn, y1: pad.t - (axis ? 12 : 0), y2: h - pad.b }, svg);
      if (axis) el("text", { class: "nowtxt", x: xn - 5, y: pad.t - 6, "text-anchor": "end" }, svg).textContent = "өчигдөр";
      if (axis) el("text", { class: "nowtxt", x: xn + 5, y: pad.t - 6, fill: "var(--ghost)", style: "fill:var(--ghost)" }, svg).textContent = "таамаг";
    }
    if (axis) {
      const step = Math.max(1, Math.round(history.length / 6));
      for (let i = 0; i < history.length - step / 2; i += step)
        el("text", { class: "tick", x: X(i) + bw / 2, y: h - 4, "text-anchor": "middle" }, svg).textContent = md(history[i].d);
    }
  }

  /** Model-ийн алдааг baseline-тай харьцуулах бүлэглэсэн багана */
  function bars(box, rows, keys, names, label) {
    const { svg, w, h } = svgFor(box, label);
    const pad = { l: 8, r: 8, t: 14, b: 44 };
    const max = Math.max(...rows.flatMap((r) => keys.map((k) => r[k]))) * 1.12;
    const gw = (w - pad.l - pad.r) / rows.length, bw = Math.min(30, (gw - 24) / keys.length);
    rows.forEach((r, i) => {
      const gx = pad.l + i * gw + (gw - bw * keys.length) / 2;
      keys.forEach((k, j) => {
        const bh = (r[k] / max) * (h - pad.t - pad.b);
        el("rect", { class: "bar" + (j === 0 ? " mine" : ""), x: gx + j * bw + 2, y: h - pad.b - bh, width: bw - 4, height: bh }, svg);
        el("text", { class: "lbl" + (j === 0 ? "" : " m"), x: gx + j * bw + bw / 2, y: h - pad.b - bh - 5, "text-anchor": "middle", "font-size": 10 }, svg).textContent = r[k].toFixed(2);
      });
      el("text", { class: "lbl m", x: pad.l + i * gw + gw / 2, y: h - pad.b + 17, "text-anchor": "middle" }, svg).textContent = `${r.h} өдрийн дараа`;
    });
    keys.forEach((k, j) => {
      const x = pad.l + j * ((w - pad.l) / keys.length);
      el("rect", { class: "bar" + (j === 0 ? " mine" : ""), x, y: h - 12, width: 10, height: 10 }, svg);
      el("text", { class: "lbl m", x: x + 15, y: h - 3 }, svg).textContent = names[j];
    });
  }

  /** Сургалтын муруй: train vs validation алдаа */
  function curve(box, pts, best, label) {
    const { svg, w, h } = svgFor(box, label);
    const pad = { l: 40, r: 10, t: 14, b: 26 };
    const xs = pts.map((p) => p.it), ys = pts.flatMap((p) => [p.train, p.valid]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys) * 0.95, y1 = Math.max(...ys) * 1.02;
    const X = (v) => pad.l + ((v - x0) / (x1 - x0)) * (w - pad.l - pad.r);
    const Y = (v) => pad.t + (1 - (v - y0) / (y1 - y0)) * (h - pad.t - pad.b);
    for (let i = 0; i <= 4; i++) {
      const v = y0 + (i / 4) * (y1 - y0);
      el("line", { class: "grid", x1: pad.l, x2: w - pad.r, y1: Y(v), y2: Y(v) }, svg);
      el("text", { class: "tick", x: pad.l - 6, y: Y(v) + 4, "text-anchor": "end" }, svg).textContent = v.toFixed(2);
      const xv = Math.round(x0 + (i / 4) * (x1 - x0));
      el("text", { class: "tick", x: X(xv), y: h - 6, "text-anchor": "middle" }, svg).textContent = xv;
    }
    el("line", { class: "best", x1: X(best), x2: X(best), y1: pad.t, y2: h - pad.b }, svg);
    el("text", { class: "nowtxt", x: X(best) + 5, y: pad.t + 2 }, svg).textContent = "early stopping";
    el("path", { class: "tr", d: "M" + pts.map((p) => `${X(p.it)},${Y(p.train)}`).join(" L") }, svg);
    el("path", { class: "va", d: "M" + pts.map((p) => `${X(p.it)},${Y(p.valid)}`).join(" L") }, svg);
  }

  /** Feature importance: хэвтээ багана */
  function hbars(box, rows, label) {
    const { svg, w, h } = svgFor(box, label);
    const lw = 130, max = Math.max(...rows.map((r) => r.gain)), rh = (h - 4) / rows.length;
    rows.forEach((r, i) => {
      const y = 2 + i * rh, bw = (r.gain / max) * (w - lw - 44);
      el("text", { class: "lbl m", x: lw - 10, y: y + rh / 2 + 4, "text-anchor": "end" }, svg).textContent = r.f;
      el("rect", { class: "bar" + (i === 0 ? " mine" : ""), x: lw, y: y + rh * 0.28, width: bw, height: rh * 0.44 }, svg);
      el("text", { class: "lbl", x: lw + bw + 8, y: y + rh / 2 + 4 }, svg).textContent = r.gain + "%";
    });
  }

  window.Charts = { wave, bars, curve, hbars, fmt };
})();
