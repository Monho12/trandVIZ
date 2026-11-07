// Хөнгөн SVG график — гадны сан ашиглахгүй (CPU, RAM бага).
(function () {
  const NS = "http://www.w3.org/2000/svg";

  // Хуудсанд нэг удаа: "ирээдүй" бүсийн зураасан хээ
  const defs = document.createElementNS(NS, "svg");
  defs.setAttribute("width", "0"); defs.setAttribute("height", "0");
  defs.setAttribute("aria-hidden", "true"); defs.style.position = "absolute";
  defs.innerHTML = `<defs><pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <line x1="0" y1="0" x2="0" y2="7" stroke="#263052" stroke-width="3"/></pattern></defs>`;
  document.body.prepend(defs);

  const fmt = (v) => {
    if (v >= 1e6) return (v / 1e6).toFixed(v >= 1e7 ? 0 : 1).replace(/\.0$/, "") + " сая";
    if (v >= 1e3) return (v / 1e3).toFixed(v >= 1e4 ? 0 : 1).replace(/\.0$/, "") + " мян";
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

  /** Түүх + таамгийн график. opts: {history, forecast, axis, pulse, label} */
  function series(box, opts) {
    const { history, forecast = [], axis = false, pulse = false, label } = opts;
    const { svg, w, h } = svgFor(box, label);
    const pad = axis ? { l: 46, r: 12, t: 16, b: 24 } : { l: 2, r: 2, t: 4, b: 4 };
    const all = history.map((p) => p.v).concat(forecast.flatMap((f) => [f.lo, f.hi]));
    const ly = (v) => Math.log10(Math.max(v, 1));
    let y0 = Math.min(...all.map(ly)), y1 = Math.max(...all.map(ly));
    if (y1 - y0 < 0.3) { y0 -= 0.15; y1 += 0.15; }
    const n = history.length + forecast.length;
    const X = (i) => pad.l + (i / (n - 1)) * (w - pad.l - pad.r);
    const Y = (v) => pad.t + (1 - (ly(v) - y0) / (y1 - y0)) * (h - pad.t - pad.b);
    const last = history.length - 1;

    if (axis) {
      const g = el("g", { class: "grid axis" }, svg);
      for (let e = Math.ceil(y0); e <= Math.floor(y1); e++) {
        for (const m of [1, 3]) {
          const v = m * 10 ** e;
          if (ly(v) < y0 || ly(v) > y1) continue;
          el("line", { x1: pad.l, x2: w - pad.r, y1: Y(v), y2: Y(v) }, g);
          el("text", { x: pad.l - 8, y: Y(v) + 4, "text-anchor": "end" }, g).textContent = fmt(v);
        }
      }
      const step = Math.max(1, Math.round(n / 6));
      const dates = history.map((p) => p.d).concat(forecast.map((f) => f.d));
      for (let i = 0; i < n - 3; i += step)
        el("text", { x: X(i), y: h - 6, "text-anchor": "middle" }, g).textContent = md(dates[i]);
    }

    // Ирээдүйн бүс (зураасан)
    if (forecast.length) el("rect", { class: "future", x: X(last), y: pad.t, width: X(n - 1) - X(last) + pad.r, height: h - pad.t - pad.b }, svg);

    // Түүхийн муруй ба доорх бүдэг талбай
    const pts = history.map((p, i) => `${X(i).toFixed(1)},${Y(p.v).toFixed(1)}`);
    el("path", { class: "area", d: `M${X(0)},${h - pad.b} L${pts.join(" L")} L${X(last)},${h - pad.b} Z` }, svg);
    const line = el("path", { class: "hist", d: "M" + pts.join(" L") }, svg);

    if (forecast.length) {
      // Итгэлийн бүс (80%)
      const top = forecast.map((f, j) => `${X(last + 1 + j)},${Y(f.hi)}`);
      const bot = forecast.map((f, j) => `${X(last + 1 + j)},${Y(f.lo)}`).reverse();
      el("path", { class: "band", d: `M${X(last)},${Y(history[last].v)} L${top.join(" L")} L${bot.join(" L")} Z` }, svg);
      const cpts = [`${X(last)},${Y(history[last].v)}`].concat(forecast.map((f, j) => `${X(last + 1 + j)},${Y(f.y)}`));
      el("path", { class: "cast", d: "M" + cpts.join(" L") }, svg);
      if (axis) forecast.forEach((f, j) => el("circle", { class: "castdot", cx: X(last + 1 + j), cy: Y(f.y), r: 3 }, svg));
    }

    // "Одоо" шугам
    el("line", { class: "nowline", x1: X(last), x2: X(last), y1: pad.t, y2: h - pad.b }, svg);
    if (axis) el("text", { class: "nowlabel", x: X(last) + 6, y: pad.t + 10 }, svg).textContent = "Одоо";
    if (pulse) el("circle", { class: "pulse", cx: X(last), cy: Y(history[last].v), r: 4 }, svg);
    el("circle", { class: "nowdot", cx: X(last), cy: Y(history[last].v), r: axis ? 4 : 2.5 }, svg);

    line.style.setProperty("--len", Math.ceil(line.getTotalLength()));
  }

  /** Model-ийн алдааг baseline-тай харьцуулах бүлэглэсэн багана */
  function bars(box, rows, keys, names, label) {
    const { svg, w, h } = svgFor(box, label);
    const pad = { l: 8, r: 8, t: 8, b: 40 };
    const max = Math.max(...rows.flatMap((r) => keys.map((k) => r[k]))) * 1.15;
    const gw = (w - pad.l - pad.r) / rows.length, bw = Math.min(28, (gw - 20) / keys.length);
    rows.forEach((r, i) => {
      const gx = pad.l + i * gw + (gw - bw * keys.length) / 2;
      keys.forEach((k, j) => {
        const bh = (r[k] / max) * (h - pad.t - pad.b);
        el("rect", { class: "bar" + (j === 0 ? " mine" : ""), x: gx + j * bw + 1, y: h - pad.b - bh, width: bw - 3, height: bh, rx: 2 }, svg);
        el("text", { class: "lbl" + (j === 0 ? "" : " m"), x: gx + j * bw + bw / 2, y: h - pad.b - bh - 5, "text-anchor": "middle", "font-size": 10 }, svg).textContent = r[k].toFixed(2);
      });
      el("text", { class: "lbl m", x: pad.l + i * gw + gw / 2, y: h - pad.b + 18, "text-anchor": "middle" }, svg).textContent = `+${r.h} өдөр`;
    });
    const lg = el("g", {}, svg);
    keys.forEach((k, j) => {
      const x = pad.l + j * ((w - pad.l) / keys.length);
      el("rect", { class: "bar" + (j === 0 ? " mine" : ""), x, y: h - 12, width: 10, height: 10, rx: 2 }, lg);
      el("text", { class: "lbl m", x: x + 14, y: h - 3 }, lg).textContent = names[j];
    });
  }

  /** Сургалтын муруй: train vs validation алдаа */
  function curve(box, pts, best, label) {
    const { svg, w, h } = svgFor(box, label);
    const pad = { l: 40, r: 10, t: 10, b: 26 };
    const xs = pts.map((p) => p.it), ys = pts.flatMap((p) => [p.train, p.valid]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys) * 0.95, y1 = Math.max(...ys) * 1.02;
    const X = (v) => pad.l + ((v - x0) / (x1 - x0)) * (w - pad.l - pad.r);
    const Y = (v) => pad.t + (1 - (v - y0) / (y1 - y0)) * (h - pad.t - pad.b);
    const g = el("g", { class: "grid axis" }, svg);
    for (let i = 0; i <= 4; i++) {
      const v = y0 + (i / 4) * (y1 - y0);
      el("line", { x1: pad.l, x2: w - pad.r, y1: Y(v), y2: Y(v) }, g);
      el("text", { x: pad.l - 6, y: Y(v) + 4, "text-anchor": "end" }, g).textContent = v.toFixed(2);
    }
    for (let i = 0; i <= 4; i++) {
      const v = Math.round(x0 + (i / 4) * (x1 - x0));
      el("text", { x: X(v), y: h - 6, "text-anchor": "middle" }, g).textContent = v;
    }
    el("line", { class: "best", x1: X(best), x2: X(best), y1: pad.t, y2: h - pad.b }, svg);
    el("text", { class: "nowlabel", x: X(best) + 5, y: pad.t + 10 }, svg).textContent = "early stop";
    el("path", { class: "tr", d: "M" + pts.map((p) => `${X(p.it)},${Y(p.train)}`).join(" L") }, svg);
    el("path", { class: "va", d: "M" + pts.map((p) => `${X(p.it)},${Y(p.valid)}`).join(" L") }, svg);
  }

  /** Feature importance: хэвтээ багана */
  function hbars(box, rows, label) {
    const { svg, w, h } = svgFor(box, label);
    const lw = 120, max = Math.max(...rows.map((r) => r.gain));
    const rh = (h - 4) / rows.length;
    rows.forEach((r, i) => {
      const y = 2 + i * rh;
      el("text", { class: "lbl m", x: lw - 8, y: y + rh / 2 + 4, "text-anchor": "end" }, svg).textContent = r.f;
      const bw = (r.gain / max) * (w - lw - 40);
      el("rect", { class: "bar" + (i === 0 ? " mine" : ""), x: lw, y: y + 3, width: bw, height: rh - 6, rx: 2 }, svg);
      el("text", { class: "lbl", x: lw + bw + 6, y: y + rh / 2 + 4 }, svg).textContent = r.gain + "%";
    });
  }

  window.Charts = { series, bars, curve, hbars, fmt };
})();
