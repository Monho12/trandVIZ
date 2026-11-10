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
  const md = window.Words.md;
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

  // Хуудсанд нэг удаа: баганын налуу өнгө (gradient) ба таамгийн зураасан хээ
  const defs = document.createElementNS(NS, "svg");
  defs.setAttribute("width", "0"); defs.setAttribute("height", "0"); defs.setAttribute("aria-hidden", "true");
  defs.style.position = "absolute";
  defs.innerHTML = `<defs>
    <linearGradient id="g-blue" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3d8ef0"/><stop offset="1" stop-color="#2a78d6"/></linearGradient>
    <linearGradient id="g-blue-soft" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8fbcf2"/><stop offset="1" stop-color="#bcd6f6"/></linearGradient>
    <pattern id="p-cast" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" fill="#f9c5c9"/><line x1="0" y1="0" x2="0" y2="6" stroke="#e63946" stroke-width="3"/></pattern>
  </defs>`;
  document.body.prepend(defs);

  /**
   * Баганан график: өдөр бүр нэг багана, тэгээс эхэлнэ.
   * Цэнхэр = бодит уншилт, улаан = таамагласан уншилт; нимгэн шугам = таамгийн 80% бүс.
   */
  function columns(box, opts) {
    const { history, forecast = [], axis = false, label, normal, day } = opts;   // day: asof өдрийн нэр (Words.day)
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
      const b = el("path", { class: "bar " + (axis ? (i === H - 1 ? "b-grad" : "b-grad-soft") : "b-blue"), d: colPath(X(i), Y(p.v), bw, base - Y(p.v)) }, svg);
      b.style.setProperty("--i", i);
    });
    forecast.forEach((f, j) => {
      const i = H + j, x = X(i);
      const b = el("path", { class: "bar " + (axis ? "b-hatch" : "b-forecast"), d: colPath(x, Y(f.y), bw, base - Y(f.y)) }, svg);
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
      // Ердийн өдрийн түвшин: "×N дахин" гэдгийг нүдээр харуулна
      if (normal) {
        el("line", { class: "norm", x1: pad.l, x2: X(H - 1) + bw, y1: Y(normal), y2: Y(normal) }, svg);
        el("text", { class: "val2", x: pad.l + 4, y: Y(normal) - 6 }, svg).textContent = `ердийн өдөр ≈ ${fmt(normal)}`;
      }
      // Оргил өдөр сүүлийн (asof) өдөр биш бол түүнийг тэмдэглэнэ
      let pk = 0; history.forEach((p, i) => { if (p.v > history[pk].v) pk = i; });
      if (pk < H - 2 && history[pk].v > 1.5 * history[H - 1].v) {
        const px = X(pk) + bw / 2, py = Y(history[pk].v);
        el("circle", { class: "peak", cx: px, cy: py - 10, r: 3 }, svg);
        el("text", { class: "val2", x: px - 8, y: py - 7, "text-anchor": "end" }, svg).textContent = `оргил ${md(history[pk].d)}: ${fmt(history[pk].v)}`;
      }
      // Сонгомол шошго: сүүлийн (asof) өдрийн утга
      const lx = X(H - 1) + bw / 2, lv = history[H - 1].v;
      el("text", { class: "val", x: lx, y: Y(lv) - 6, "text-anchor": F ? "end" : "middle" }, svg).textContent = `${day || md(history[H - 1].d)} ${fmt(lv)}`;
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
        ? `<b>${longDate(d.d)}, таамаг</b>≈ ${fmt(d.y)} уншилт<br><span>10 удаагийн 8-д: ${fmt(d.lo)} – ${fmt(d.hi)}</span><br><span>${window.Words.TIP.forecastBar}</span>`
        : `<b>${longDate(d.d)}</b>${fmt(d.v)} уншилт`;
      r.addEventListener("pointermove", (e) => { hl.setAttribute("x", X(i) - (slot - bw) / 2); hl.setAttribute("visibility", "visible"); showTip(e, html); });
      r.addEventListener("pointerleave", () => { hl.setAttribute("visibility", "hidden"); hideTip(); });
    }
  }

  /** Dumbbell: horizon бүр нэг мөр. Цэнхэр цэг = манай model, саарал цэг = энгийн арга,
   *  хоёр цэгийн утга шошготой, мөрийн төгсгөлд сайжралт ("−13%"). rows: [{name, model, naive, gain}] */
  function dumbbell(box, rows, { names = {}, fmt: f = (v) => v.toFixed(1) + "%", label } = {}) {
    const { svg, w, h } = svgFor(box, label);
    const narrow = w < 420;
    const pad = { l: narrow ? 88 : 118, r: narrow ? 62 : 72, t: 8, b: 24 };
    const max = Math.max(...rows.map((r) => Math.max(r.model, r.naive)));
    const step = niceStep(max, 5), top = Math.ceil((max * 1.04) / step) * step;
    const X = (v) => pad.l + (v / top) * (w - pad.l - pad.r), rh = (h - pad.t - pad.b) / rows.length;
    for (let v = 0; v <= top + 1e-9; v += step) {
      el("line", { class: v ? "grid" : "base", x1: X(v), x2: X(v), y1: pad.t, y2: h - pad.b }, svg);
      el("text", { class: "tick", x: X(v), y: h - 6, "text-anchor": "middle" }, svg).textContent = `${+v.toFixed(1)}%`;
    }
    rows.forEach((r, i) => {
      const y = pad.t + rh * (i + 0.5), xm = X(r.model), xn = X(r.naive);
      const g = el("g", {}, svg);
      el("rect", { x: 0, y: y - rh / 2, width: w, height: rh, fill: "transparent" }, g);   // hover талбай (цэгээс том)
      el("text", { class: "val2", x: pad.l - 12, y: y + 4, "text-anchor": "end", "font-size": narrow ? 12 : 13 }, g).textContent = r.name;
      el("line", { class: "db-bar", x1: xm, x2: xn, y1: y, y2: y }, g);
      el("circle", { class: "db-naive", cx: xn, cy: y, r: 6 }, g);
      el("circle", { class: "db-model", cx: xm, cy: y, r: 6 }, g);
      // Утга цэгийн гадна талд: model (бага алдаа) зүүн талд, энгийн арга баруун талд -> хэзээ ч давхцахгүй
      el("text", { class: "val", x: Math.min(xm, xn) - 10, y: y + 4, "text-anchor": "end" }, g).textContent = f(r.model);
      el("text", { class: "val2", x: Math.max(xm, xn) + 10, y: y + 4 }, g).textContent = f(r.naive);
      el("text", { class: "db-gain", x: w - 2, y: y + 5, "text-anchor": "end" }, g).textContent = `−${Math.round(r.gain)}%`;
      const html = `<b>${r.name}</b>${names.model}: ${f(r.model)} зөрдөг<br><span>${names.naive}: ${f(r.naive)}</span><br><span>Алдаа ${Math.round(r.gain)}% бага</span>`;
      g.addEventListener("pointermove", (e) => showTip(e, html));
      g.addEventListener("pointerleave", hideTip);
    });
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

  /** Энгийн босоо багана: hi = тодруулах багануудын индекс, base = дундаж шугам (жишээ нь 100) */
  function bars(box, values, { labels = [], hi = [], valLabels = {}, base, minY = 0, label } = {}) {
    const { svg, w, h } = svgFor(box, label);
    const pad = { t: 22, b: 22 }, n = values.length, slot = w / n, bw = Math.max(2, slot * 0.68);
    const max = Math.max(...values), lo = minY, Y = (v) => h - pad.b - ((v - lo) / (max - lo)) * (h - pad.t - pad.b);
    values.forEach((v, i) => {
      const x = i * slot + (slot - bw) / 2, y = Y(Math.max(v, lo));
      el("path", { class: hi.includes(i) ? "b-blue" : "b-soft", d: colPath(x, y, bw, h - pad.b - y) }, svg);
      if (valLabels[i] != null) el("text", { class: "val", x: x + bw / 2, y: y - 6, "text-anchor": "middle" }, svg).textContent = valLabels[i];
      if (labels[i]) el("text", { class: "tick", x: x + bw / 2, y: h - 5, "text-anchor": "middle" }, svg).textContent = labels[i];
    });
    if (base != null) el("line", { class: "norm", x1: 0, x2: w, y1: Y(base), y2: Y(base) }, svg);
    el("line", { class: "base", x1: 0, x2: w, y1: h - pad.b, y2: h - pad.b }, svg);
  }

  /** Хэвтээ багана, утгатай: эхний hiN нь тод цэнхэр */
  function hbarsV(box, rows, { fmt: f = fmt, hiN = 1, label, lw: lwMax = 170, stackBelow = 0 } = {}) {
    const { svg, w, h } = svgFor(box, label);
    const stack = w < stackBelow;   // нарийн: нэр баганын дээр, багана бүтэн өргөнөөр
    const lw = stack ? 0 : Math.min(lwMax, w * 0.42), max = Math.max(...rows.map((r) => r.v)), rh = h / rows.length;
    rows.forEach((r, i) => {
      const bh = Math.min(stack ? 12 : 18, rh * (stack ? 0.32 : 0.62));
      const y = i * rh, bw = Math.max(2, (r.v / max) * (w - lw - 56)), by = stack ? y + rh - bh - 6 : y + (rh - bh) / 2;
      el("text", stack ? { class: i < hiN ? "val" : "val2", x: 0, y: by - 6, "font-size": 13 }
        : { class: i < hiN ? "val" : "tick", x: lw - 10, y: y + rh / 2 + 4, "text-anchor": "end", "font-size": 13 }, svg).textContent = r.name;
      const bar = el("rect", { class: r.cls || (i < hiN ? "b-blue" : "b-soft"), x: lw, y: by, width: bw, height: bh, rx: 4 }, svg);
      el("text", { class: i < hiN ? "val" : "val2", x: lw + bw + 8, y: by + bh / 2 + 4 }, svg).textContent = f(r.v);
      if (r.tip) {
        const hit = el("rect", { x: 0, y, width: w, height: rh, fill: "transparent" }, svg);
        hit.addEventListener("pointermove", (e) => showTip(e, r.tip));
        hit.addEventListener("pointerleave", hideTip);
        bar.setAttribute("aria-label", r.name + ": " + f(r.v));
      }
    });
  }

  /** Олон шугам (3 хүртэл), нэрийг шугамын оргил дээр шууд бичнэ */
  function lines(box, months, series, { label } = {}) {
    const { svg, w, h } = svgFor(box, label);
    const pad = { l: 0, r: 0, t: 22, b: 22 }, keys = Object.keys(series), cls = ["l-c1", "l-c2", "l-c3"];
    const max = Math.max(...keys.flatMap((k) => series[k]));
    const X = (i) => pad.l + (i / (months.length - 1)) * (w - pad.l - pad.r);
    const Y = (v) => h - pad.b - (v / max) * (h - pad.t - pad.b);
    el("line", { class: "base", x1: 0, x2: w, y1: h - pad.b, y2: h - pad.b }, svg);
    months.forEach((m, i) => { if (m.endsWith("-01")) el("text", { class: "tick", x: X(i), y: h - 5, "text-anchor": "middle" }, svg).textContent = m.slice(0, 4); });
    keys.forEach((k, j) => {
      const v = series[k];
      el("path", { class: cls[j], d: "M" + v.map((y, i) => `${X(i).toFixed(1)},${Y(y).toFixed(1)}`).join(" L") }, svg);
    });
  }

  /** Squarified treemap: тэгш өнцөгтүүдийг аль болох дөрвөлжин байлгаж хуваана */
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
  // Өсөлтийн өнгө: цэнхэр = буурсан, саарал = ердийн, улаан = шуугиж байна
  const HEAT = [[0.67, "#2a78d6", "#fff"], [0.9, "#a9c9f0", "#13294b"], [1.5, "#eef1f5", "#1D3557"],
    [2.5, "#fbd5d8", "#5c1219"], [5, "#f4a3a9", "#4a0e14"], [15, "#e63946", "#fff"], [Infinity, "#b5222e", "#fff"]];
  const heat = (r) => HEAT.find((h) => r < h[0]);

  function treemap(box, items, { onPick, emoji = {}, label } = {}) {
    box.innerHTML = "";
    const w = box.clientWidth, h = box.clientHeight;
    const n = w < 600 ? 14 : items.length;   // утсан дээр цөөн, том хайрцаг
    const rects = squarify(items.map((d) => ({ ...d, v: d.views })).sort((a, b) => b.v - a.v).slice(0, n), 0, 0, w, h);
    rects.forEach((r, i) => {
      const [, bg, fg] = heat(r.ratio);
      const a = document.createElement("a");
      a.className = "tm-cell";
      a.href = "#/topic/" + encodeURIComponent(r.article);
      a.style.cssText = `left:${r.x}px;top:${r.y}px;width:${r.w}px;height:${r.h}px;background:${bg};color:${fg};--i:${i}`;
      a.setAttribute("aria-label", `${r.title}: ${fmt(r.views)} уншилт, ердийнхөөс ×${r.ratio}`);
      const big = r.w > 120 && r.h > 70, mid = r.w > 56 && r.h > 34;
      if (mid) a.innerHTML = `<span class="tm-t${big ? " tm-big" : ""}">${emoji[r.category] || ""} ${r.title}</span>` +
        (big ? `<span class="tm-v">${fmt(r.views)}, ×${r.ratio}</span>` : "");
      a.addEventListener("pointermove", (e) => showTip(e, `<b>${r.title}</b>${fmt(r.views)} уншилт<br><span>Ердийнхөөс ×${r.ratio}</span>`));
      a.addEventListener("pointerleave", hideTip);
      box.appendChild(a);
    });
    box.setAttribute("role", "list"); box.setAttribute("aria-label", label || "");
  }

  /** Жижиг sparkline: сүүлийн 30 хоног, сүүлийн (asof) өдрийн цэг тод */
  function spark(box, history) {
    const { svg, w, h } = svgFor(box, "");
    svg.setAttribute("aria-hidden", "true");
    const max = Math.max(...history.map((p) => p.v)) || 1, n = history.length;
    const X = (i) => 2 + (i / (n - 1)) * (w - 6), Y = (v) => h - 2 - (v / max) * (h - 6);
    const pts = history.map((p, i) => `${X(i).toFixed(1)},${Y(p.v).toFixed(1)}`);
    el("path", { class: "sp-area", d: `M${X(0)},${h - 1} L${pts.join(" L")} L${X(n - 1)},${h - 1} Z` }, svg);
    el("path", { class: "sp-line", d: "M" + pts.join(" L") }, svg);
    el("circle", { class: "sp-dot", cx: X(n - 1), cy: Y(history[n - 1].v), r: 2.5 }, svg);
  }

  window.Charts = { columns, dumbbell, curve, bars, hbarsV, lines, treemap, spark, heat: HEAT, fmt, longDate, md };
})();
