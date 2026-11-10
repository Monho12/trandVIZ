// "Бүх сэдэв" хуудсын бүлэглэлт (ADR 0013): ангиллаар хэсэглэнэ, хэсэг дотор asof өдрийн уншилтаар (их -> бага).
(function (root) {
  const SHOWN = 5;   // хэсэг бүр анхандаа хэдэн мөр харуулах вэ; үлдсэн нь "Бүгдийг харах (N)"-ээр дэлгэгдэнэ
  // Тэнцсэн уншилтыг нэрээр: нүүрний ангиллын карттай (src/serve.py-ийн categories) ижил дараалал
  const byViews = (a, b) => b.views - a.views || (a.article < b.article ? -1 : a.article > b.article ? 1 : 0);
  // items: /api/trending-ийн мөрүүд, order: нүүрний ангиллын дараалал, other: "Бусад"-ын түлхүүр (үргэлж сүүлд)
  const sections = (items, order, other) => [...order, other]
    .map((key) => ({ key, topics: items.filter((t) => t.category === key).sort(byViews) }))
    .filter((s) => s.topics.length);

  const Listing = { SHOWN, sections };
  if (typeof module !== "undefined" && module.exports) module.exports = Listing;
  else root.Listing = Listing;
})(typeof window !== "undefined" ? window : globalThis);
