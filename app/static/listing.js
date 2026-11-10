// "Бүх сэдэв" хуудсын бүлэглэлт (ADR 0013): ангиллаар хэсэглэнэ, хэсэг дотор asof өдрийн уншилтаар (их -> бага).
(function (root) {
  const SHOWN = 5;   // хэсэг бүр анхандаа хэдэн мөр харуулах вэ; үлдсэн нь "Бүгдийг харах (N)"-ээр дэлгэгдэнэ
  // items: /api/trending-ийн мөрүүд, order: нүүрний ангиллын дараалал, last: "Бусад" (үргэлж сүүлд).
  // order-д байхгүй ангилал гарвал сэдэв нь алга болохгүй: order-ийн дараа, last-ийн өмнө орно.
  const sections = (items, order, last) => {
    const extra = [...new Set(items.map((t) => t.category))].filter((k) => !order.includes(k) && k !== last);
    return [...order, ...extra, last]
      .map((key) => ({ key, topics: items.filter((t) => t.category === key).sort((a, b) => b.views - a.views) }))
      .filter((s) => s.topics.length);
  };

  const Listing = { SHOWN, sections };
  if (typeof module !== "undefined" && module.exports) module.exports = Listing;
  else root.Listing = Listing;
})(typeof window !== "undefined" ? window : globalThis);
