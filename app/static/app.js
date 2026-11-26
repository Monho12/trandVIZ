// Шуугиан — энгийн hash router + хуудсууд
(function () {
  const C = window.Charts, W = window.Words, V = window.Viz;
  const main = document.getElementById("main");
  const CATS = {
    politics: ["🏛️", "Улс төр"], film_tv: ["🎬", "Кино, цуврал"], true_crime: ["🕯️", "True crime"],
    tech_ai: ["🤖", "AI, технологи"], sports: ["⚽", "Спорт"], music: ["🎵", "Хөгжим"],
    games_anime: ["🎮", "Тоглоом, anime"], celebs: ["💅", "Алдартнууд"], society: ["👥", "Нийгэм"],
    mongolia: ["🇲🇳", "Монгол"], "Бусад": ["🌐", "Бусад"],   // вирал сэдвийн ангилал (ADR 0005)
  };
  const cat = (k) => (CATS[k] || ["", k]).join(" ");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const href = (a) => "#/topic/" + encodeURIComponent(a);
  const in3 = (t) => t.forecast[t.forecast.length - 1];
  let redraws = [], rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => redraws.forEach((f) => f()), 150); });
  const draw = (fn) => { redraws.push(fn); fn(); return fn; };

  // Хүсэлт бүр нэг удаа (cache). Амжилтгүй хүсэлт cache-д үлдэхгүй: "Дахин оролдох" зөвхөн түүнийг давтана (ADR 0027).
  const cache = {};
  const api = (p) => (cache[p] ||= fetch(p).then((r) => {
    if (!r.ok) throw Object.assign(new Error(String(r.status)), { status: r.status });
    return r.json();
  }).catch((e) => { delete cache[p]; e.path = p; throw e; }));
  // Толгойн огноо ба мэдэгдэл: өгөгдөл дутуу (ADR 0022) > хуучирсан (ADR 0008)
  function meta(d) {
    document.getElementById("asof").textContent = `Өгөгдөл: ${W.longDate(d.asof)} хүртэл`;
    const s = document.getElementById("stale-note"), text = d.incomplete ? W.incompleteNote(d.incomplete, d.asof) : d.stale ? W.staleNote(d.asof, d.age_days) : "";
    s.hidden = !text;
    s.textContent = text;
  }

  // ═════════ Карт (давхарга 2, ADR 0027): нэр · ● ×N · дүгнэлт ба таамаг · spark · "Ямар нөхцөлд?" (3а) ═════════
  // ctx: { asof, T (хүчтэй өсөлтийн босго), src (track record-ын эх сурвалж эсвэл null), minN }
  const strong = (t, T) => t.measurable && t.pct != null && t.pct >= T && !t.cyclical;   // ADR 0026: тод = хүчтэй, мөчлөгийнх хэзээ ч биш
  function fcHTML(t, T) {
    if (!t.measurable) return `<span class="num" title="${esc(W.TIP.lowViews)}">${esc(W.LIST.low)}</span>`;
    const num = `<span class="num${strong(t, T) ? " bold" : ""}">${esc(`${W.arrow(t.pct)} ${W.signed(t.pct)}`)}</span>`;
    return t.cyclical && t.cycle != null ? `${num} <span class="cyc" title="${esc(W.cycleTip(t.cycle))}">· ${esc(W.CYCLE_WORD)}</span>` : num;
  }
  const verdictHTML = (t, T) => (t.verdict
    ? `<span class="w${t.verdict === "continue" ? " bold" : ""}">${esc(W.VERDICT[t.verdict])}</span> ${fcHTML(t, T)}` : fcHTML(t, T));
  const markHTML = (t, asof) => (t.anomaly
    ? `<span class="dot-mark" title="${esc(W.markTip(t, asof))}"><i aria-hidden="true">●</i>${esc(W.markText(t.ratio))}<span class="vh">: ${esc(W.markTip(t, asof))}</span></span>` : "");
  function codeTrack(t, ctx) {
    const c = ctx.src && ctx.src.by_code.find((x) => x.key === t.situation);
    if (!c) return "";
    if (!c.enough) return `<p>${esc(W.codeFew(ctx.minN))}</p>`;
    const v = t.anomaly ? c.down10 : c.excess10, b = t.anomaly ? ctx.src.base.down10 : ctx.src.base.excess10;
    const [hb, rest] = W.codeHit(v, t.anomaly);
    return `<div class="ia">${V.iconArray(v, `<b>${esc(hb)}</b>${esc(rest)}`)}${V.iconArray(b, esc(W.codeBase(b)), true)}</div>
      <p class="prov">${esc(W.prov(ctx.src, c.n))}</p>`;
  }
  const detailHTML = (t, ctx) => `<p class="code">${esc(t.situation_label)}</p><p>${esc(W.CODE_TEXT[t.situation] || "")}</p>${codeTrack(t, ctx)}<p class="disclaim">${esc(W.DISCLAIM)}</p>`;
  const slug = (a) => "c-" + a.replace(/[^A-Za-z0-9]/g, "_");
  const cardHTML = (t, ctx) => `<li class="card" id="${slug(t.article)}" data-a="${esc(t.article)}">
      <div class="c-top"><h3 class="c-name"><a href="${href(t.article)}">${esc(t.title)}</a></h3>${markHTML(t, ctx.asof)}</div>
      <p class="c-verdict">${verdictHTML(t, ctx.T)}</p>
      <div class="spark" data-a="${esc(t.article)}"></div>
      <div class="c-foot"><button class="more-btn" type="button" aria-expanded="false" aria-controls="d-${slug(t.article)}">${esc(W.MORE)}</button>
        <span class="c-dates">${esc(W.byDay(in3(t).d))}</span></div>
      <div class="detail" id="d-${slug(t.article)}" hidden>${detailHTML(t, ctx)}</div>
    </li>`;
  // Картын spark-ийг зурах, "Ямар нөхцөлд?"-ийг холбох (3а зэрэг олон дэлгэгдэнэ)
  function bindCards(root, items) {
    const byA = Object.fromEntries(items.map((t) => [t.article, t]));
    draw(() => root.querySelectorAll(".card .spark[data-a]").forEach((b) => byA[b.dataset.a] && V.spark(b, byA[b.dataset.a])));
    root.querySelectorAll(".more-btn:not([data-bound])").forEach((b) => {
      b.dataset.bound = "1";
      b.addEventListener("click", () => {
        const open = b.getAttribute("aria-expanded") !== "true";
        b.setAttribute("aria-expanded", open);
        document.getElementById(b.getAttribute("aria-controls")).hidden = !open;
      });
    });
  }
  const sum = (s) => W.homeSum(s).map(([a, n, b]) => `${esc(a)}${n == null ? "" : `<b>${n}</b>`}${esc(b || "")}`).join("");
  const byRatio = (a, b) => (b.ratio ?? 0) - (a.ratio ?? 0) || (b.pct ?? -9) - (a.pct ?? -9);   // ×N их нь эхэнд, тэнцвэл pct
  const TOP = 3;   // нүүрэнд хэсэг бүрт (ADR 0027, 2026-11-26)

  // Төлөвүүд (ADR 0027): алдаа + "Дахин оролдох" (зөвхөн хүсэлтийг давтана), cold start-ийн skeleton
  const errorBox = (e) => `<div class="state-box" role="alert"><p>${e && e.path ? `<b>${esc(W.ERROR.what)}</b> ${esc(W.ERROR.why)}` : `<b>${esc(W.ERROR.bug)}</b>`}</p>
      <p><button class="btn" type="button" data-retry>${esc(W.ERROR.retry)}</button></p>
      <p class="code">HTTP ${esc(e && (e.status || e.message))}${e && e.path ? ` · ${esc(e.path)}` : ""}</p></div>`;
  function bindRetry(root) {
    root.querySelectorAll("[data-retry]").forEach((b) => b.addEventListener("click", () => {
      b.disabled = true; b.textContent = W.ERROR.retrying;
      route({ keepScroll: true });
    }));
  }

  // ═════════ Нүүр (ADR 0022, 0027): h1 → treemap → үргэлжлэх / унтрах (top 3) → сэргэх → долоо хоногийн ердийн өсөлт ═════════
  async function home(tk) {
    const [trR, mpR, srcR] = await Promise.allSettled([api("/api/trending"), api("/api/map"), api("/api/track-record")]);
    if (!alive(tk)) return;
    if (trR.status === "rejected" && mpR.status === "rejected") throw trR.reason;
    const tr = trR.value, mp = mpR.value;
    meta(tr || mp);
    const tracks = srcR.value, src = tracks ? (tracks.sources.find((x) => x.current && x.source_key === "recomputed") || null) : null;
    const tmSec = (asof) => `<section class="tm-sec" aria-labelledby="tm-h"><h2 class="vh" id="tm-h">${esc(W.mapTitle(asof))}</h2>
      ${V.tmKey()}<div class="tmap" id="tmap"></div></section>`;
    const tmBody = mp ? tmSec(mp.asof) : `<section class="tm-sec">${errorBox(mpR.reason)}</section>`;
    if (!tr) {   // хэсэгчилсэн алдаа: treemap ажилласаар
      main.innerHTML = `<h1 class="page-h">${esc(W.mapTitle(mp.asof))}</h1>${tmBody}${errorBox(trR.reason)}`;
    } else {
      const items = tr.items, ctx = { asof: tr.asof, T: tr.T, src, minN: tracks ? tracks.min_n : null };
      const by = (v) => items.filter((t) => t.anomaly && t.verdict === v).sort(byRatio);
      const s = tr.anomalies, quiet = s.n === 0;
      const group = (v) => {
        const all = by(v), id = `g-${v}`;
        return `<section class="grp" aria-labelledby="${id}"><h2 class="grp-h" id="${id}">${esc(W.GROUP[v])} (${all.length})</h2>${all.length
          ? `<ul class="cards">${all.slice(0, TOP).map((t) => cardHTML(t, ctx)).join("")}</ul>${all.length > TOP
            ? `<p class="see-all"><a href="#/list?f=${v}">${esc(W.seeAllN(all.length))}</a></p>` : ""}`
          : `<p class="neutral">${esc(W.groupEmpty(tr.asof, v))}</p>`}</section>`;
      };
      const beyond = tr.beyond.map((a) => items.find((t) => t.article === a)).filter(Boolean);
      const cyc = tr.cyclical_rise.map((a) => items.find((t) => t.article === a)).filter(Boolean);
      main.innerHTML = `<h1 class="page-h">${esc(W.homeH1(tr.asof, s.n))}</h1>${tmBody}
        <p class="sum">${sum(s)}</p>
        ${quiet ? "" : group("continue") + group("fade")}
        <section aria-labelledby="by-h"><h2 class="sec-h" id="by-h">${esc(W.reviveTitle(tr.dates))}</h2><p class="lead">${esc(W.REVIVE_LEAD)}</p>
          ${beyond.length ? `<ul class="cards">${beyond.map((t) => cardHTML(t, ctx)).join("")}</ul>` : `<p class="neutral">${esc(W.REVIVE_EMPTY)}</p>`}</section>
        ${cyc.length ? `<details class="cyc-list"><summary>${esc(W.cycleTitle(cyc.length))}</summary><div><p class="neutral">${esc(W.CYCLE_LEAD)}</p>
          <ul class="rowlist">${cyc.map((t) => `<li><a href="${href(t.article)}">${esc(t.title)}</a><span>${fcHTML(t, tr.T)}</span></li>`).join("")}</ul></div></details>` : ""}`;
      bindCards(main, items);
    }
    bindRetry(main);
    if (mp) draw(() => {
      V.treemap(document.getElementById("tmap"), mp.items, { asof: mp.asof, href, onCell: (a, e) => {
        const card = document.getElementById(slug(a));   // нэг tap = нэг үйлдэл: карт нь нүүрэнд байвал карт руу, үгүй бол сэдвийн хуудас
        if (card) { e.preventDefault(); V.flash(card); }
      } });
      V.linkHover(main);
    });
  }

  // ═════════ Бүх сэдэв (ADR 0013, 0027): шүүлтүүр Бүгд / Үргэлжлэх / Унтрах, эрэмбэ. Хоёул URL-д: #/list?f=continue&s=views ═════════
  const LIST_SHOWN = 30;
  async function list(q, tk) {
    const [tr, tracks] = await Promise.all([api("/api/trending"), api("/api/track-record").catch(() => null)]);
    if (!alive(tk)) return;
    meta(tr);
    const L = W.LIST, has = (arr, k) => arr.some(([x]) => x === k);
    const f = has(L.filters, q.get("f")) ? q.get("f") : "all", srt = has(L.sorts, q.get("s")) ? q.get("s") : "views";
    const SORT = { views: (a, b) => b.views - a.views, up: (a, b) => (b.pct ?? -9) - (a.pct ?? -9) || b.views - a.views,
      down: (a, b) => (a.pct ?? 9) - (b.pct ?? 9) || b.views - a.views };
    const items = tr.items.filter((t) => f === "all" || (t.anomaly && t.verdict === f)).sort(SORT[srt]);
    const src = tracks ? (tracks.sources.find((x) => x.current && x.source_key === "recomputed") || null) : null;
    const ctx = { asof: tr.asof, T: tr.T, src, minN: tracks ? tracks.min_n : null };
    const link = (ff, ss) => `#/list?f=${ff}&s=${ss}`;
    const seg = (label, id, opts, cur, to) => `<div class="ctl"><span class="lbl" id="${id}">${esc(label)}</span><div class="seg" role="group" aria-labelledby="${id}">${opts.map(([k, n]) =>
      `<a href="${to(k)}" aria-current="${k === cur}">${esc(n)}</a>`).join("")}</div></div>`;
    main.innerHTML = `<h1 class="page-h">${esc(L.title)}</h1><p class="lead">${esc(L.lead(tr.asof, tr.items.length, tr.dates))}</p>
      <div class="sortbar">${seg(L.filterLabel, "f-l", L.filters, f, (k) => link(k, srt))}${seg(L.sortLabel, "s-l", L.sorts, srt, (k) => link(f, k))}</div>
      ${items.length ? `<ul class="cards" id="lcards">${items.slice(0, LIST_SHOWN).map((t) => cardHTML(t, ctx)).join("")}</ul>
        ${items.length > LIST_SHOWN ? `<p class="more-rows"><button class="btn ghost" type="button" id="lmore">${esc(L.more(items.length - LIST_SHOWN))}</button></p>` : ""}`
        : `<p class="neutral">${esc(L.none(tr.asof, f))}</p>`}`;
    bindCards(main, items);
    document.getElementById("lmore")?.addEventListener("click", (e) => {
      document.getElementById("lcards").insertAdjacentHTML("beforeend", items.slice(LIST_SHOWN).map((t) => cardHTML(t, ctx)).join(""));
      e.target.closest("p").remove();
      bindCards(main, items);
    });
  }

  // ═════════ Сэдвийн хуудас (3б, ADR 0026, 0027): 2–3 мөр текст, 60 хоногийн гол график (180 сэлгэгч), replay, "Ямар нөхцөлд?" ═════════
  async function topic(article, tk) {
    const T = W.TOPIC;
    let t;
    try { t = await api("/api/topic/" + encodeURIComponent(article)); } catch (e) {
      if (e.status !== 404) throw e;
      if (!alive(tk)) return;
      main.innerHTML = `<a class="back" href="#/">${esc(T.back)}</a><h1 class="topic-h">${esc(article.replace(/_/g, " "))}</h1><p class="lead">${esc(T.missing)}</p>`;
      return;
    }
    const tracks = await api("/api/track-record").catch(() => null);
    if (!alive(tk)) return;
    meta(t);
    const src = tracks ? (tracks.sources.find((x) => x.current && x.source_key === "recomputed") || null) : null;
    const ctx = { asof: t.asof, T: t.T, src, minN: tracks ? tracks.min_n : null };
    const view = { days: 60, rp: null };
    const anomOf = Object.fromEntries((t.anom || []).map((a) => [a.d, a.r]));
    main.innerHTML = `<a class="back" href="#/">${esc(T.back)}</a>
      <h1 class="topic-h">${esc(t.title)}</h1><p class="topic-cat">${esc(catOnly(t.category))}</p>
      <p class="t-lines">${markHTML(t, t.asof)}<span>${esc(T.dayLine(t, t.asof, C.fmt))}</span></p>
      <p class="t-lines"><span class="c-verdict">${verdictHTML(t, ctx.T)}</span><span>${esc(T.fcLine(in3(t), C.fmt))}</span></p>
      <p class="t-iv">${esc(T.iv80(t.interval))}</p>
      <div class="panel">
        <div class="ch-head"><h2 class="ch-title">${esc(T.chart)}</h2>
          <div class="seg" role="group" aria-label="${esc(T.rangeLabel)}">${T.range.map(([n, l]) => `<button type="button" data-days="${n}" aria-pressed="${n === 60}">${esc(l)}</button>`).join("")}</div></div>
        <div class="main-ch" id="main-ch"></div>
        <ul class="key"><li><i class="k-act"></i>${esc(T.key.act)}</li><li><i class="k-fc"></i>${esc(T.key.fc)}</li><li><i class="k-band"></i>${esc(T.key.band)}</li>
          <li><i class="k-dot"></i>${esc(T.key.dot)}</li><li><i class="k-norm"></i>${esc(T.key.norm)}</li><li><i class="k-base"></i>${esc(T.key.base)}</li>
          <li id="rp-key" hidden><i class="k-rp"></i>${esc(T.key.rp)}</li></ul>
        <section class="replay" aria-labelledby="rp-h"><h3 id="rp-h">${esc(T.replay)}</h3>
          <div class="rp-ctl"><label class="vh" for="rp-sel">${esc(T.dayLabel)}</label>
            <select id="rp-sel" disabled><option value="">${esc(T.loading)}</option></select>
            <button class="btn ghost" type="button" id="rp-prev" aria-label="${esc(T.prev)}" disabled>←</button>
            <button class="btn ghost" type="button" id="rp-next" aria-label="${esc(T.next)}" disabled>→</button></div>
          <p class="rp-note" id="rp-note" hidden>${esc(T.only60)}</p>
          <div class="rp-out" id="rp-out" aria-live="polite"></div></section>
        <details class="tbl"><summary>${esc(T.table)}</summary><div class="tbl-wrap"><table class="data"><caption class="vh">${esc(T.caption)}</caption>
          <thead><tr>${T.cols.map((c) => `<th scope="col">${esc(c)}</th>`).join("")}</tr></thead><tbody>
          ${t.history.slice(-14).map((d) => `<tr><td>${W.md(d.d)}</td><td>${C.fmt(d.v)}</td><td></td><td></td><td></td><td>${d.d in anomOf ? esc(`● ×${anomOf[d.d]}`) : ""}</td></tr>`).join("")}
          ${t.forecast.map((f) => `<tr><td>${W.md(f.d)}</td><td></td><td>${C.fmt(f.y)}</td><td>${C.fmt(f.lo)}</td><td>${C.fmt(f.hi)}</td><td></td></tr>`).join("")}</tbody></table></div></details>
      </div>
      <section class="panel" aria-labelledby="cond-h"><h2 class="ch-title" id="cond-h">${esc(W.MORE)}</h2><div class="detail flat">${detailHTML(t, ctx)}</div></section>
      <p class="neutral">${esc(W.NEUTRAL)}</p>`;
    const box = document.getElementById("main-ch");
    const chart = () => V.mainChart(box, t, view);
    draw(chart);
    const sel = document.getElementById("rp-sel"), out = document.getElementById("rp-out");
    function setDays(n) {
      view.days = n;
      main.querySelectorAll("[data-days]").forEach((b) => b.setAttribute("aria-pressed", +b.dataset.days === n));
      document.getElementById("rp-note").hidden = n === 60;
      document.getElementById("rp-key").hidden = !(view.rp && n === 60);
      chart();
    }
    main.querySelectorAll("[data-days]").forEach((b) => b.addEventListener("click", () => setDays(+b.dataset.days)));
    // Өнгөрсөн таамаг: сэргээж тооцсон (ADR 0015), сэдвийн хуудаснаас тусдаа ачаална (нэг сэдэвт хэдэн секунд)
    let rps = [];
    function bandOutcome(r) {
      const b = src && src.by_band.find((x) => x.key === T.bandKey(r.pct));
      if (!b || r.pct == null) return "";
      const [k, what] = T.bandWhat(b.key), v = k === "down" ? b.down10 : k === "up" ? b.up10 : 1 - b.up10 - b.down10;
      const [x, y, z] = T.bandLine(b.label, v, what);
      return `<div class="ia">${V.iconArray(v, `${esc(x)}<b>${esc(y)}</b>${esc(z)}`)}</div><p class="prov">${esc(W.prov(src, b.n))}</p>`;
    }
    function setRp(asof) {
      const r = rps.find((x) => x.asof === asof) || null;
      view.rp = r; sel.value = r ? r.asof : "";
      if (r) {
        const act = t.history.find((h) => h.d === r.forecast[r.forecast.length - 1].d);
        const [said, got] = T.outcome(r, act, C.fmt);
        out.innerHTML = `<p>${esc(said)}${got ? ` ${esc(got[0])}<b>${esc(got[1])}</b>${esc(got[2])}` : ""}</p>${bandOutcome(r)}<p class="rp-note">${esc(T.notOne)}</p>`;
      } else out.innerHTML = "";
      setDays(r ? 60 : view.days);
    }
    sel.addEventListener("change", () => setRp(sel.value));
    const step = (k) => { const i = rps.findIndex((r) => r === view.rp); setRp(rps[Math.max(0, Math.min(rps.length - 1, i < 0 ? 0 : i + k))].asof); };
    document.getElementById("rp-prev").addEventListener("click", () => step(1));    // rps: шинээс хуучин руу
    document.getElementById("rp-next").addEventListener("click", () => step(-1));
    try {
      const d = await api("/api/topic/" + encodeURIComponent(article) + "/replay");
      if (!alive(tk)) return;
      rps = d.items;
      sel.innerHTML = `<option value="">${esc(T.pick)}</option>${rps.map((r) => `<option value="${r.asof}">${esc(T.option(r))}</option>`).join("")}`;
      [sel, ...main.querySelectorAll("#rp-prev, #rp-next")].forEach((x) => { x.disabled = !rps.length; });
    } catch (e) {
      if (!alive(tk)) return;
      sel.closest(".rp-ctl").outerHTML = errorBox(e);
      main.querySelector(".replay [data-retry]")?.addEventListener("click", () => { route({ keepScroll: true }); });
    }
  }

  // ═════════ Загвар ═════════
  // Feature-ийн энгийн монгол нэр (meta.json-ийн нэрээс)
  const FEAT = { ratio_7: "7 хоногийн дунджаас хэр зөрж байна", roll_std_3: "Сүүлийн 3 өдрийн савлагаа",
    growth_1: "Өмнөх өдрөөс хэр өссөн", vs_level: "Ердийн түвшнээсээ хэр дээр", dow: "Гарагийн өдөр",
    growth_3: "3 өдрийн өсөлт", roll_std_7: "7 хоногийн савлагаа", roll_std_14: "14 хоногийн савлагаа",
    roll_std_28: "28 хоногийн савлагаа", roll_mean_7: "7 хоногийн дундаж", roll_max_28: "28 хоногийн оргил",
    from_max_28: "28 хоногийн оргилоос хэр доор", days_since_peak: "Оргилоос хойш хэдэн хоног",
    doy_sin: "Жилийн аль үе", doy_cos: "Жилийн аль үе", level_365: "Жилийн ердийн түвшин", month: "Сар", is_weekend: "Амралтын өдөр эсэх" };
  // ═════════ "Загвар" (ADR 0027, Майк 2026-11-26): график түрүүлнэ, хүснэгт нөөцөнд. Гарчиг = асуулт, нэг мөр дүгнэлт, саарал тайлбар ═════════
  const tableHTML = (head, rows) => `<details class="tbl"><summary>${esc(W.PROOF.table)}</summary><div class="tbl-wrap"><table class="data">
    <thead><tr>${head.map((x) => `<th scope="col">${esc(x)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${r.map((x) => `<td>${esc(x)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
  function proofHTML(src) {
    const P = W.PROOF, pc = P.pc, v = (k) => src.by_verdict.find((x) => x.key === k), ab = src.anomaly_base;
    const verdict = (k, big) => {
      const x = v(k), w = P[k];
      if (!x) return "";
      return `<section class="pf${big ? " hero" : ""}" aria-labelledby="pf-${k}"><h2 id="pf-${k}">${esc(w.q)}</h2><p class="say">${esc(w.say(x))}</p>
        ${V.compare([{ label: w.model, v: x.hit, n: x.n }, { label: w.base, v: x.base_hit, n: ab.n, base: true }], big)}
        <p class="prov">${esc(w.what)} ${esc(P.nOf(x.n, ab.n))} · ${esc(W.prov(src))}</p>
        ${tableHTML(["", "%", "n"], [[w.model, pc(x.hit), num(x.n)], [w.base, pc(x.base_hit), num(ab.n)]])}</section>`;
    };
    const bands = src.by_band, codes = [...src.by_code].sort((a, b) => (b.up10 - b.down10) - (a.up10 - a.down10));
    const ok = codes.filter((c) => c.enough), best = ok[0], worst = [...ok].sort((a, b) => b.down10 - a.down10)[0];
    return `${verdict("continue", true)}${verdict("fade", false)}
      <section class="pf" aria-labelledby="pf-bands"><h2 id="pf-bands">${esc(P.bands.q)}</h2><p class="say">${esc(P.bands.say(bands[0], bands[bands.length - 1]))}</p>
        <ul class="key"><li><i class="k-up"></i>${esc(P.bands.up)}</li><li><i class="k-dn"></i>${esc(P.bands.down)}</li></ul>
        <div class="stair" id="pf-stair"></div><p class="axis-t">${esc(P.bands.axis)}</p>
        <p class="prov">${esc(P.bands.what)} · ${esc(W.prov(src))}</p>
        ${tableHTML(["", P.bands.up, P.bands.down, "n"], bands.map((b) => [b.label, pc(b.up10), pc(b.down10), num(b.n)]))}</section>
      <section class="pf" aria-labelledby="pf-codes"><h2 id="pf-codes">${esc(P.codes.q)}</h2>${best && worst ? `<p class="say">${esc(P.codes.say(best, worst))}</p>` : ""}
        ${V.diverge(codes)}
        <p class="prov">${esc(P.codes.what)} · ${esc(W.prov(src))}</p>
        ${tableHTML(["", P.bands.up, P.bands.down, "n"], codes.map((c) => [c.label, pc(c.up10), pc(c.down10), num(c.n)]))}</section>`;
  }
  const num = (n) => W.num(n);
  // Нэг жишээ: хамгийн их уншигдсан сэдвийн өнгөрсөн өдрийн таамаг (replay, ADR 0015) ба бодит
  async function example(tk, tr) {
    const box = document.getElementById("pf-ex");
    if (!box || !tr) return;
    const X = W.PROOF.example, top = [...tr.items].sort((a, b) => b.views - a.views)[0];
    let t, rp;
    try { [t, rp] = await Promise.all([api("/api/topic/" + encodeURIComponent(top.article)), api("/api/topic/" + encodeURIComponent(top.article) + "/replay")]); }
    catch (e) { if (alive(tk)) { box.innerHTML = errorBox(e); bindRetry(box); } return; }
    if (!alive(tk) || !rp.items.length) return;
    let i = 0;
    box.innerHTML = `<div class="ex-ctl"><button class="btn ghost" type="button" id="ex-prev" aria-label="${esc(X.prev)}">←</button>
        <p class="ex-day" id="ex-day" aria-live="polite"></p><button class="btn ghost" type="button" id="ex-next" aria-label="${esc(X.next)}">→</button></div>
      <p class="say" id="ex-say"></p><div class="ex-ch" id="ex-ch"></div>
      <ul class="key"><li><i class="k-act"></i>${esc(X.key.act)}</li><li><i class="k-fc"></i>${esc(X.key.fc)}</li><li><i class="k-band"></i>${esc(X.key.band)}</li></ul>
      <p class="prov">${esc(X.what)} · ${esc(rp.source)} · model ${esc(rp.model_version)}</p>
      <p class="see-all"><a href="${href(t.article)}">${esc(X.open)}</a></p>`;
    const show = () => {
      const r = rp.items[i], act = t.history.find((h) => h.d === r.forecast[r.forecast.length - 1].d), [a, b] = X.say(r, act, C.fmt);
      document.getElementById("ex-day").textContent = `${t.title} · ${X.day(r)}`;
      document.getElementById("ex-say").innerHTML = `${esc(a)}${b ? ` → <b>${esc(b)}</b>` : ""}`;
      document.getElementById("ex-prev").disabled = i >= rp.items.length - 1;
      document.getElementById("ex-next").disabled = i <= 0;
      V.replayMini(document.getElementById("ex-ch"), t, r);
    };
    document.getElementById("ex-prev").addEventListener("click", () => { i = Math.min(rp.items.length - 1, i + 1); show(); });   // items: шинээс хуучин руу
    document.getElementById("ex-next").addEventListener("click", () => { i = Math.max(0, i - 1); show(); });
    draw(show);
  }

  async function model(tk) {
    const [mR, srcR, trR] = await Promise.allSettled([api("/api/model"), api("/api/track-record"), api("/api/trending")]);
    if (!alive(tk)) return;
    if (mR.status === "rejected" && srcR.status === "rejected") throw mR.reason;
    const m = mR.value, tracks = srcR.value, tr = trR.value;
    if (m || tr) meta(m || tr);
    const src = tracks ? (tracks.sources.find((x) => x.current && x.source_key === "recomputed") || null) : null;
    const P = W.PROOF;
    main.innerHTML = `<h1 class="page-h">${esc(W.MODEL_TITLE)}</h1>
      <p class="lead">${esc(P.lead)}${src ? ` <span class="prov">${esc(P.provAll(src))}</span>` : ""}</p>
      ${src ? proofHTML(src) : tracks ? "" : errorBox(srcR.reason)}
      ${tr ? `<section class="pf" aria-labelledby="pf-ex-h"><h2 id="pf-ex-h">${esc(P.example.q)}</h2><div id="pf-ex"><div class="sk ex-sk" aria-hidden="true"></div></div></section>` : ""}
      <p class="neutral">${esc(W.NEUTRAL)}</p>
      <details class="tech" id="tech"><summary>${esc(P.tech)}</summary><div class="tech-body" id="tech-body">${m ? `<p class="lead">${esc(P.techLead)}</p>` : errorBox(mR.reason)}</div></details>`;
    bindRetry(main);
    if (src) {
      draw(() => V.stair(document.getElementById("pf-stair"), src.by_band));
      main.querySelectorAll(".cmp, .dv").forEach(V.bindTips);
      requestAnimationFrame(() => requestAnimationFrame(() => main.classList.add("grown")));   // нэг хөдөлгөөн: баганууд ургана
    }
    example(tk, tr);
    if (!m) return;
    const tech = document.getElementById("tech");
    tech.addEventListener("toggle", () => { if (tech.open && !tech.dataset.drawn) { tech.dataset.drawn = "1"; technical(m); } });
  }

  // Техникийн хэсэг (хаалттай, нээхэд зурагдана): skill score + 95% интервал, өмнөх "Загвар" хуудасны графикууд
  function technical(m) {
    const p = m.pipeline, v = m.valid, N = m.names;
    const mdl = esc(N.model), nv = esc(N.naive);
    const h3 = m.metrics.find((r) => r.h === 3), e = Math.round(h3[m.winner]);
    const rows = m.metrics.map((r) => ({ name: `${r.h} өдрийн дараа`, model: r[m.winner], naive: r.naive, gain: m.skill["h" + r.h].point }));
    const others = v.algos.filter((a) => a !== m.winner), order = [m.winner, ...others];
    const spread = Math.max(...v.rows.map((r) => Math.max(...v.algos.map((a) => r[a])) - Math.min(...v.algos.map((a) => r[a]))));
    const vsNaive = Math.min(...v.rows.map((r) => r.naive - r[m.winner]));
    const T = W.modelWords(m), steps = T.steps;   // хуудасны үг (#34): words.js
    document.getElementById("tech-body").insertAdjacentHTML("beforeend", `
      <section class="pf flat" aria-labelledby="sk-h"><h2 id="sk-h">${esc(W.PROOF.skill.q)}</h2><p class="say">${esc(W.PROOF.skill.say(m.skill))}</p>
        <div class="skill" id="m-skill"></div><p class="prov">${esc(W.PROOF.skill.what)}</p></section>
      <p class="chart-sub">Сайтын ард ажиллаж буй model: <b>${esc(m.live.algo_name)}</b> ${esc(m.live.version)}, сургасан ${W.longDate(m.live.trained_at, m.live.data_asof)},
        өгөгдөл ${W.longDate(m.live.data_asof)} хүртэл, таамаг ${esc(m.dates)}</p>
      <div class="mgrid">
        <div class="mcard">
          <h3>Таамаг хэр зөрдөг вэ?</h3>
          <p class="big">3 өдрийн дараах таамаг "${nv}" аргаас <b>${Math.round(m.skill.h3.point)}%</b> бага алддаг.</p>
          <p class="chart-sub">100 гэж таамагласан бол бодит нь ихэвчлэн ~${100 - e}–${100 + e} орчим.</p>
          <ul class="key">
            <li><i class="k-dot"></i>${mdl}</li>
            <li><i class="k-dot k-dot-gray"></i>${nv}</li>
          </ul>
          <div class="mchart db" id="m-err"></div>
          <p class="note">${nv}: 3 өдрийн дараа ч анхаарал өнөөдрийнхтэй адилхан байна гэж таах хамгийн энгийн арга. Model үүнээс бага алдах ёстой.</p>
          <p class="hint">${esc(T.errHint)}</p>
        </div>
        <div class="mcard">
          <h3>Overfit болсон уу? <span class="h-sub">(${m.curve_h} өдрийн дараах model)</span></h3>
          <p class="chart-sub">${esc(T.overfitSub)}</p>
          <div class="mchart" id="m-curve"></div>
          <p class="note">${esc(T.overfitNote)}</p>
        </div>
      </div>

      <section class="sec" aria-labelledby="pl-h">
        <h2 id="pl-h">Яаж хийсэн бэ?</h2>
        <p class="lead">Карт дээр дарж дэлгэрэнгүйг үзнэ үү.</p>
        <ol class="pl">${steps.map((st, i) => `
          <li class="pl-step">
            <button class="pl-card" aria-expanded="false" aria-controls="pl-more-${i}" data-i="${i}">
              <span class="pl-n">${i + 1}</span>
              <span class="pl-t">${esc(st.title)}</span>
              <span class="pl-v">${esc(st.value)}</span><span class="pl-u">${esc(st.unit)}</span>
              <span class="pl-l">${esc(st.line)}</span>
            </button>
            <p class="pl-more" id="pl-more-${i}" hidden>${esc(st.more)}</p>
          </li>`).join("")}
        </ol>
        <p class="pl-panel" id="pl-panel" aria-live="polite" hidden></p>
      </section>

      <section class="sec" aria-labelledby="why-h">
        <h2 id="why-h">Яагаад ${esc(p.algo_name)}?</h2>
        <p class="lead">Алгоритмаас илүү feature чухал байсан.</p>
        <div class="mgrid">
          <div class="mcard">
            <h3>Шударга уралдаан</h3>
            <ul class="why">
              <li>Гурвуулаа ижил өгөгдөл, ижил <b>${p.n_features}</b> feature, ${esc(T.fairBudget)}</li>
              <li>${esc(T.fairRule)} <b>Test-ийг ашиглаагүй.</b></li>
              <li>Гурав бараг ижил: хоорондоо ${spread.toFixed(2)} нэгжээс бага зөрдөг, харин "${nv}"-аас ${vsNaive.toFixed(1)}+ нэгж бага.</li>
            </ul>
            <p class="chart-h">${esc(T.algoChart)}</p>
            <div class="mchart" id="m-algo" style="height:150px"></div>
          </div>
          <div class="mcard">
            <h3>${esc(T.tableTitle)}</h3>
            <table class="fc vt">
              <caption>${esc(T.tableCaption)}</caption>
              <thead><tr><th>Арга</th>${v.rows.map((r) => `<th>${r.h} өдөр</th>`).join("")}<th>Дундаж</th></tr></thead>
              <tbody>${order.map((a) => `<tr class="${a === m.winner ? "y" : ""}"><td>${esc(N[a])}</td>${v.rows.map((r) => `<td>${r[a].toFixed(2)}%</td>`).join("")}<td>${v.mean[a].toFixed(2)}%</td></tr>`).join("")}
                <tr class="nv"><td>${nv}</td>${v.rows.map((r) => `<td>${r.naive.toFixed(2)}%</td>`).join("")}<td>${v.mean.naive.toFixed(2)}%</td></tr></tbody>
            </table>
            <p class="hint">Сонголтын дүрэм (дундаж лог MAE): ${order.map((a) => `${esc(N[a])} ${v.mean_log[a].toFixed(5)}`).join(" · ")}</p>
            <ul class="why str">${order.map((a) => `<li><b>${esc(N[a])}</b> ${esc(T.strength[a] || "")}</li>`).join("")}</ul>
          </div>
          <div class="mcard" style="grid-column:1/-1">
            <h3>Model юуг хамгийн их хардаг вэ? <span class="h-sub">(эхний 5)</span></h3>
            <p class="chart-sub">${esc(T.importanceSub)}</p>
            <div class="mchart" id="m-imp" style="height:220px"></div>
          </div>
        </div>
      </section>`);

    draw(() => V.skillCI(document.getElementById("m-skill"), m.skill));
    draw(() => C.dumbbell(document.getElementById("m-err"), rows, { names: N, label: `${N.model} ба ${N.naive}: алдааг хувиар, 1–3 өдрийн дараа` }));
    draw(() => C.curve(document.getElementById("m-curve"), m.curve, m.best_iter, `Сургалт ба validation алдааны муруй, ${m.curve_h} өдрийн дараах model`));
    draw(() => C.hbarsV(document.getElementById("m-algo"), [...order, "naive"].map((a) => ({
      name: N[a], v: v.mean[a], cls: a === m.winner ? "b-blue" : a === "naive" ? "b-naive" : "b-gray",
      tip: `<b>${esc(N[a])}</b>Дунджаар ${v.mean[a].toFixed(2)}% зөрдөг` })),
      { fmt: (x) => x.toFixed(2) + "%", hiN: 1, lw: 150, label: T.algoChartLabel }));
    draw(() => C.hbarsV(document.getElementById("m-imp"), m.importance_share.slice(0, 5).map((r) => ({
      name: FEAT[r.f] || r.f, v: r.share, cls: "b-blue", tip: `<b>${esc(FEAT[r.f] || r.f)}</b>${r.share}% <span>(${esc(r.f)})</span>` })),
      { fmt: (x) => x.toFixed(1) + "%", hiN: 0, lw: 260, stackBelow: 560, label: "Feature importance, эхний 5" }));

    // Алхмын карт: утсанд картын доор, том дэлгэцэнд мөрийн доорх нэг талбайд дэлгэрнэ
    const cards = [...main.querySelectorAll(".pl-card")], panel = document.getElementById("pl-panel");
    cards.forEach((b) => b.addEventListener("click", () => {
      const open = b.getAttribute("aria-expanded") !== "true";
      cards.forEach((c) => { c.setAttribute("aria-expanded", "false"); c.nextElementSibling.hidden = true; });
      if (open) { b.setAttribute("aria-expanded", "true"); b.nextElementSibling.hidden = false; }
      panel.hidden = !open;
      panel.innerHTML = open ? `<b>${esc(steps[+b.dataset.i].title)}.</b> ${esc(steps[+b.dataset.i].more)}` : "";
    }));
  }

  // ═════════ Хэв маяг (өмнө нь "Сонирхолтой", ADR 0022) ═════════
  async function facts(tk) {
    const d = await api("/api/insights");
    if (!alive(tk)) return;
    document.getElementById("stale-note").hidden = true;
    const R = d.ranges, bold = (s) => `<b>${esc(s)}</b>`;
    const dec3 = Math.round(d.decay[3]);
    const top2 = d.categories.slice(0, 2);
    const picks = d.weekday_pick, off = (k) => d.weekday[k].map((v) => v - 100);   // 100 = долоо хоногийн дундаж
    const lim = Math.max(...picks.flatMap((p) => off(p.key).map(Math.abs)));       // хоёр графикт нэг тэнхлэг
    const mn = d.mongolia[0], H = d.holidays;
    main.innerHTML = `
      <h1 class="page-h">Хэв маяг</h1>
      <p class="lead">${esc(W.factsLead(R.decay, d.topics_n))}</p>
      <div class="fgrid">
        <section class="fcard">
          <h3>Шуугиан хэр хурдан мартагддаг вэ?</h3>
          <p class="big"><b>${dec3}%</b> нь л 3 хоногийн дараа үлддэг</p>
          <p class="fnote">${esc(W.decayNote(d.decay_n))}</p>
          <div class="fchart" id="f-decay"></div>
        </section>
        <section class="fcard">
          <h3>Дэлхий юуг хамгийн их уншдаг вэ?</h3>
          <p class="big">${W.catsHeadline(top2.map((c) => bold(catShort(c.key))), top2.map((c) => c.views))}</p>
          <p class="fnote">${esc(W.catsNote(d.curated_n, R.categories))}</p>
          <div class="fchart" id="f-cats" style="height:250px"></div>
        </section>
        <section class="fcard wide">
          <h3>Аль гарагт юу уншдаг вэ?</h3>
          <p class="big">${W.weekdayTitle(picks, Object.fromEntries(picks.map((p) => [p.key, bold(catShort(p.key))])))}</p>
          <p class="fnote">${esc(W.WEEKDAY_NOTE)}</p>
          <div class="minis">${picks.map((p) => `
            <div><p class="mini-h">${cat(p.key)}</p><div class="fchart mini" data-k="${p.key}"></div></div>`).join("")}
          </div>
        </section>
        <section class="fcard">
          <h3>Баяр жил бүр давтагддаг</h3>
          <p class="big">${esc(W.HOLIDAY_TITLE)}</p>
          <p class="fnote">${esc(W.holidayNote(R.holidays, H.incomplete_year))}</p>
          <div class="fchart" id="f-hol"></div>
        </section>
        <section class="fcard">
          <h3>Дэлхий Монголын юуг уншдаг вэ?</h3>
          <p class="big"><b>${Math.round(mn.share)}%</b> нь ${esc(MN[mn.title] || mn.title)}</p>
          <p class="fnote">${esc(W.mongoliaNote(d.mongolia_n, R.mongolia))}</p>
          <div class="fchart" id="f-mn" style="height:220px"></div>
        </section>
      </div>`;
    draw(() => C.bars(document.getElementById("f-decay"), d.decay, {
      labels: d.decay.map((_, i) => (i === 0 ? "оргил" : [3, 7, 14].includes(i) ? `${i} хоног` : "")),
      hi: [0, 3], valLabels: { 0: "100%", 3: `${dec3}%`, 7: `${Math.round(d.decay[7])}%` }, label: "Оргилын дараах өдрүүдэд уншилт хэдэн хувь үлддэг вэ" }));
    draw(() => C.hbarsV(document.getElementById("f-cats"), d.categories.map((c) => ({ name: catOnly(c.key), v: c.views })),
      { fmt: C.fmt, hiN: 1, label: `Ангилал бүрийн уншилт, ${W.span(R.categories)}` }));
    draw(() => picks.forEach((p) => C.diverging(main.querySelector(`.mini[data-k="${p.key}"]`), off(p.key), {
      labels: W.DAYS, hi: p.peak, lim, label: `${catOnly(p.key)}: гараг бүр долоо хоногийн дунджаас хэдэн хувиар зөрдөг вэ, ${W.span(R.weekday)}`,
      marks: { [p.peak]: W.weekdayLabel(p.peak, d.weekday[p.key][p.peak]), [p.low]: W.weekdayLabel(p.low, d.weekday[p.key][p.low]) } })));
    draw(() => C.lines(document.getElementById("f-hol"), H.months, H.series, { label: "Баярын нийтлэлүүдийн сар бүрийн өдрийн дундаж уншилт",
      marks: Object.fromEntries(Object.entries(H.peaks).map(([k, month]) => [k, { month, text: W.holidayLabel(HOL[k] || k, month) }])) }));
    draw(() => C.hbarsV(document.getElementById("f-mn"), d.mongolia.map((r) => ({ name: MN[r.title] || r.title, v: r.share })),
      { fmt: (v) => Math.round(v) + "%", hiN: 1, label: `Монголын сэдвүүдийн эзлэх хувь, ${W.span(R.mongolia)}` }));
  }
  const catShort = (k) => catOnly(k).split(",")[0];   // өгүүлбэр дотор: "AI, технологи" -> "AI" (таслал өгүүлбэрийг эвдэхгүй)
  const HOL = { Christmas: "Зул сар", "Valentine's Day": "Валентин" };   // Halloween орчуулгагүй
  const catOnly = (k) => (CATS[k] || ["", k])[1];
  const MN = { "Genghis Khan": "Чингис хаан", Mongolia: "Монгол Улс", "Mongol Empire": "Монголын эзэнт гүрэн",
    "Kublai Khan": "Хубилай хаан", "Golden Horde": "Алтан Орд", Ulaanbaatar: "Улаанбаатар", Mongols: "Монголчууд", "Ögedei Khan": "Өгөдэй хаан" };

  // ═════════ Router ═════════
  // Cold start (ADR 0011, 0027): Render free унтаж байвал анхны хүсэлт удаан. Skeleton нь картын хэмжээтэй (layout үсрэхгүй),
  // SLOW_MS-ийн дараа шударга мэдэгдэл + хүлээсэн секунд. Хүлээлтийн хугацааг хэмжээгүй тул тоо амлахгүй.
  const SLOW_MS = 1500;
  const skeleton = () => `<div class="sk sk-h" aria-hidden="true"></div><div class="sk sk-map" aria-hidden="true"></div>
    <div class="state-box" role="status" id="sk-msg" hidden><p>${esc(W.COLD)}</p><p class="code" id="sk-t"></p></div>
    <ul class="cards" aria-hidden="true">${'<li class="sk sk-card"></li>'.repeat(3)}</ul>`;
  let token = 0;
  const alive = (tk) => tk === token;   // хуудас солигдсон бол хуучин хүсэлтийн хариу шинэ хуудсыг дарж бичихгүй
  async function route({ keepScroll = false } = {}) {
    const tk = ++token;
    redraws = [];
    V.hideTip();
    const [path, qs] = location.hash.replace(/^#\/?/, "").split("?");
    const [page, arg] = path.split("/");
    const name = ["list", "model", "topic", "facts"].includes(page) ? page : "home";
    document.querySelectorAll(".nav a").forEach((a) =>
      a.dataset.route === name ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
    const y = scrollY, t0 = Date.now();
    main.innerHTML = skeleton();
    const tick = setInterval(() => {
      const box = document.getElementById("sk-msg");
      if (!box) return;
      const ms = Date.now() - t0;
      box.hidden = ms < SLOW_MS;
      document.getElementById("sk-t").textContent = W.waited(Math.round(ms / 1000));
    }, 250);
    try {
      if (name === "list") await list(new URLSearchParams(qs || ""), tk);
      else if (name === "facts") await facts(tk);
      else if (name === "model") await model(tk);
      else if (name === "topic") await topic(decodeURIComponent(arg || ""), tk);
      else await home(tk);
    } catch (e) {
      if (alive(tk)) { main.innerHTML = errorBox(e); bindRetry(main); }
      if (!e.path) console.error(e);   // кодын алдаа (хүсэлтийн биш): тестэд харагдана
    } finally {
      clearInterval(tick);
    }
    if (!alive(tk)) return;
    if (name !== "home") main.focus({ preventScroll: true });
    window.scrollTo(0, keepScroll ? y : 0);
  }
  window.addEventListener("hashchange", () => route());
  route();
})();
