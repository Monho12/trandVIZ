// PROTOTYPE — throwaway. Доод хувилбар сэлгэгч (← → товч, гарын сум) + variant panel (toggle, тохиолдол, хэмжилт, JSON export).
// Сонголт URL-д хадгалагдана (reload-д тогтвортой, хуваалцаж болно). Persistence байхгүй: JSON файлыг татаж хадгална.
(function () {
  const A = window.App, S = A.S, bar = document.getElementById("pt-bar"), panel = document.getElementById("pt-panel");
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let notes = "";

  function drawBar() {
    const i = A.VARIANTS.findIndex(([k]) => k === S.v), [, name] = A.VARIANTS[i];
    bar.innerHTML = `<button type="button" data-d="-1" aria-label="Өмнөх хувилбар">←</button>
      <span class="pt-lab">${esc(name)}</span>
      <button type="button" data-d="1" aria-label="Дараагийн хувилбар">→</button>
      <button type="button" class="pt-open" aria-expanded="${!panel.hidden}" aria-controls="pt-panel">Сонголт</button>`;
    bar.querySelectorAll("[data-d]").forEach((b) => b.addEventListener("click", () => cycle(+b.dataset.d)));
    bar.querySelector(".pt-open").addEventListener("click", () => { panel.hidden = !panel.hidden; drawBar(); if (!panel.hidden) drawPanel(); });
  }
  function cycle(d) {
    const i = A.VARIANTS.findIndex(([k]) => k === S.v), n = A.VARIANTS.length;
    A.setVariant(A.VARIANTS[(i + d + n) % n][0]); drawBar(); if (!panel.hidden) drawPanel();
  }
  addEventListener("keydown", (e) => {
    const t = e.target;
    if (t.closest && t.closest("input, textarea, select, [contenteditable], svg")) return;
    if (e.key === "ArrowLeft") cycle(-1); else if (e.key === "ArrowRight") cycle(1);
  });

  function exportObj() {
    const m = A.measure();
    const labels = {};
    A.GROUPS.forEach((g) => g.items.forEach((i) => { labels[i.k] = { name: i.name, value: S.o[i.k], label: i.opts.find((o) => o[0] === S.o[i.k])[1],
      default: i.opts[0][0], changed: S.o[i.k] !== i.opts[0][0] }; }));
    return {
      prototype: "W7 #52 · 1-р шат (бүтэц) · theme 1", exported_at: new Date().toISOString(),
      variant: { key: S.v, name: A.VARIANTS.find(([k]) => k === S.v)[1] },
      choices: labels, case: S.case, notes,
      url: location.href, viewport: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio, ua: navigator.userAgent },
      reduced_motion: matchMedia("(prefers-reduced-motion: reduce)").matches, measurements: m,
    };
  }
  function download() {
    const blob = new Blob([JSON.stringify(exportObj(), null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `w7-prototype-choice-${S.v}-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a); a.click(); a.remove();
  }

  function measHTML(m) {
    if (!m) return "";
    const L = { viewport: "Дэлгэц", page: "Хуудас", h_overflow: "Хэвтээ гүйлгэлт", nav_rows: "Цэсний мөр", nav_min_h: "Цэсний зүйлийн өндөр (px)",
      small_targets: "< 44px target", h1_lines: "h1 мөр", cards_total: "Карт нийт", cards_first_screen: "Эхний дэлгэцэд бүтэн карт",
      first_card_top_px: "Эхний картын дээд (px)", spark_band_px_median: "Spark band h3 медиан (px)", spark_band_px_min: "Spark band h3 хамгийн бага (px)",
      cycle_word_wraps: "Мөчлөгийн мөр 2 мөрт орсон", treemap_h: "Treemap өндөр (px)", topic_days: "Горим (хоног)", topic_mark: "Mark",
      topic_band_h3_px: "Гол графикийн band h3 (px)", topic_peak_over_last: "Оргил ÷ сүүлийн өдөр", topic_chart_w: "Графикийн өргөн (px)" };
    const bad = (k, v) => (k === "h_overflow" && v) || (k === "small_targets" && v > 0) || (k === "nav_min_h" && v < 44) || (/band.*px/.test(k) && v < 4);
    return `<table>${Object.entries(m).filter(([k]) => k !== "small_targets_list").map(([k, v]) =>
      `<tr><td>${esc(L[k] || k)}</td><td class="${bad(k, v) ? "warn" : ""}">${esc(typeof v === "boolean" ? (v ? "тийм" : "үгүй") : v)}</td></tr>`).join("")}</table>
      ${m.small_targets ? `<p class="pt-note warn">${esc(m.small_targets_list.join(" · "))}</p>` : ""}`;
  }
  function drawPanel() {
    panel.innerHTML = `<button class="pt-x" type="button" aria-label="Хаах">×</button>
      <h2>W7 prototype · 1-р шат (бүтэц)</h2>
      <p class="pt-note">Throwaway. "санал" = UI grill-ийн санал (анхдагч). Эргэлзсэнээ л солино. ← → товч хувилбар сэлгэнэ.</p>
      <h3>Хувилбар (бүтэн)</h3>
      <fieldset><div class="pt-opts">${A.VARIANTS.map(([k, n]) => `<label class="pt-o"><input type="radio" name="pt-v" value="${k}" ${S.v === k ? "checked" : ""}>${esc(n)}</label>`).join("")}</div></fieldset>
      <h3>Хүнд тохиолдол (өгөгдөл)</h3>
      <select id="pt-case">${A.CASES.map(([k, n]) => `<option value="${k}" ${S.case === k ? "selected" : ""}>${esc(n)}</option>`).join("")}</select>
      ${S.case === "cold" ? `<p class="pt-note">Хүлээлт <input type="number" id="pt-cold" min="1" max="180" value="${S.cold}"> сек (зохиомол). Бодит хэмжилт хийгээгүй: Render-ийг энэ орчноос нээж чадаагүй (ADR 0027). HTML нь өөрөө унтдаг серверээс ирэх эрсдэлийг энэ prototype харуулахгүй.</p>` : ""}
      ${S.case === "error" || S.case === "partial" ? `<p class="pt-note"><label><input type="checkbox" id="pt-retry" ${S.retryOk ? "checked" : ""}> "Дахин оролдох" амжилттай болно</label></p>` : ""}
      ${S.case === "quiet" ? `<p class="pt-note">Valid-ийн 271 өдөрт Anomaly 0-тэй өдөр гараагүй (#54): 11.10-аас anomaly-г арилгасан зохиомол.</p>` : ""}
      <div class="pt-acts"><button type="button" id="pt-again">Тохиолдлыг дахин эхлүүлэх</button></div>
      ${A.GROUPS.map((g) => `<h3>${esc(g.name)}</h3>${g.items.map((i) => `<fieldset><legend>${esc(i.name || i.k)}</legend><div class="pt-opts">${i.opts.map(([v, n], j) =>
        `<label class="pt-o${j === 0 ? " def" : ""}"><input type="radio" name="pt-${i.k}" value="${v}" ${S.o[i.k] === v ? "checked" : ""}>${esc(n)}</label>`).join("")}</div></fieldset>`).join("")}`).join("")}
      <p class="pt-note">Хэвтээ tick нэг л утгатай: replay "хэвтээ tick" ба мөчлөг "h3 tick" зэрэг сонгогдвол мөчлөг шошго болно.</p>
      <h3>Хэмжилт (энэ дэлгэц)</h3><div id="pt-meas">${measHTML(A.meas.last)}</div>
      <h3>Тэмдэглэл</h3><textarea id="pt-notes" placeholder="Юу таалагдсан, юу эргэлзээтэй…">${esc(notes)}</textarea>
      <div class="pt-acts"><button type="button" class="pri" id="pt-dl">JSON татах</button><button type="button" id="pt-copy">JSON хуулах</button>
        <button type="button" id="pt-link">Холбоос хуулах</button><button type="button" id="pt-reset">Бүгдийг санал руу</button></div>
      <p class="pt-note" id="pt-msg" role="status"></p>`;
    panel.querySelector(".pt-x").addEventListener("click", () => { panel.hidden = true; drawBar(); });
    panel.querySelectorAll('input[name="pt-v"]').forEach((r) => r.addEventListener("change", () => { A.setVariant(r.value); drawBar(); }));
    panel.querySelector("#pt-case").addEventListener("change", (e) => { A.setCase(e.target.value); drawPanel(); });
    panel.querySelector("#pt-cold")?.addEventListener("change", (e) => A.setCold(Math.max(1, +e.target.value || 20)));
    panel.querySelector("#pt-retry")?.addEventListener("change", (e) => { S.retryOk = e.target.checked; });
    panel.querySelector("#pt-again").addEventListener("click", () => A.restartSim());
    A.GROUPS.forEach((g) => g.items.forEach((i) => panel.querySelectorAll(`input[name="pt-${i.k}"]`).forEach((r) =>
      r.addEventListener("change", () => A.set(i.k, r.value)))));
    panel.querySelector("#pt-notes").addEventListener("input", (e) => { notes = e.target.value; });
    const msg = (t) => { panel.querySelector("#pt-msg").textContent = t; };
    panel.querySelector("#pt-dl").addEventListener("click", () => { download(); msg("Татсан. Файлыг docs/ui-tests/ эсвэл issue #52-т хавсаргана."); });
    panel.querySelector("#pt-copy").addEventListener("click", () => navigator.clipboard.writeText(JSON.stringify(exportObj(), null, 2)).then(() => msg("Хуулсан."), () => msg("Clipboard ажилласангүй: JSON татах-ыг ашиглана уу.")));
    panel.querySelector("#pt-link").addEventListener("click", () => navigator.clipboard.writeText(location.href).then(() => msg("Холбоос хуулсан."), () => msg(location.href)));
    panel.querySelector("#pt-reset").addEventListener("click", () => { A.reset(); drawPanel(); });
  }
  A.onMeasure = (m) => { const box = document.getElementById("pt-meas"); if (box) box.innerHTML = measHTML(m); };
  window.PT = { exportObj, open() { panel.hidden = false; drawBar(); drawPanel(); } };
  drawBar();
  A.start();
})();
