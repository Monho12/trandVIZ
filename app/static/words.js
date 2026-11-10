// Сайтын үг ба шошго (ADR 0014): тоо = "уншилт", таамгийн хувь = "анхаарал"; ▲ = өнгөрсөн, ↗/🔥 = таамаг.
// "Өчигдөр" гэдэг үг зөвхөн эндээс, asof = өчигдөр (age_days = 1) үед л гарна; бусад үед огноо ("11/9").
// asof: "YYYY-MM-DD", age: /api/*-ийн age_days (хэрэглэгчийн өнөөдөр − asof).
(function (root) {
  const md = (s) => { const [, m, d] = s.split("-"); return `${+m}/${+d}`; };
  const isYesterday = (age) => age === 1;
  const day = (asof, age) => (isYesterday(age) ? "өчигдөр" : md(asof));
  const dayTile = (asof, age) => (isYesterday(age) ? "Өчигдөр" : md(asof));
  const homeTitle = (asof, age) => `${isYesterday(age) ? "Өчигдөр" : md(asof) + "-нд"} дэлхий юуг уншив?`;

  // ▲ шошго: урт "өчигдөр ×3" / "11/8 ×3", богино "×3" (▲ тэмдгийг CSS нэмнэ). Tooltip үргэлж огноотой.
  const surgeText = (ratio, asof, age, short) => (short ? `×${ratio}` : `${day(asof, age)} ×${ratio}`);
  const surgeTip = (ratio, asof) => `${md(asof)}-нд ердийн өдрөөс ${ratio} дахин их уншигдсан`;

  // API-ийн "80%: +10% … +85%" -> "10 удаагийн 8-д: +10% … +85%"
  const interval = (text) => (text ? text.replace(/^80%:\s*/, "10 удаагийн 8-д: ") : "");
  // API-ийн "— (өчигдөр уншилтгүй)" шошгыг хуучирсан өгөгдөлд огноотой болгоно
  const forecastLabel = (label, asof, age) => (isYesterday(age) ? label : label.replace("өчигдөр", `${md(asof)}-нд`));

  const TIP = {
    attention: "Анхаарал: Wikipedia-ийн нийт уншилтад эзлэх хувь",
    interval: "80% интервал: model-ийн өмнөх алдаанаас тооцсон хүрээ",
    normal: "ердийн түвшин (медиан): сүүлийн 2 сарын уншилт, сүүлийн 7 хоногийг оруулаагүй",
    forecastBar: "таамагласан уншилт (Wikipedia-ийн нийт уншилт өөрчлөгдөхгүй гэж үзвэл)",
    table: "Доод–Дээд: 10 удаагийн 8-д бодит тоо энэ хооронд байдаг (80% интервал).",
  };

  const Words = { md, day, dayTile, homeTitle, surgeText, surgeTip, interval, forecastLabel, TIP };
  if (typeof module !== "undefined" && module.exports) module.exports = Words;
  else root.Words = Words;
})(typeof window !== "undefined" ? window : globalThis);
