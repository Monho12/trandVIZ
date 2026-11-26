# forecast-log

Хадгалсан таамгийн өдөр тутмын log (ADR 0016). `.github/workflows/forecast-log.yml` (main) өдөр бүр 06:41, 09:41 UTC-д бичнэ.
Энэ branch-ийг гараар бүү засаарай: зөвхөн нэмэгддэг, `main`-д merge хийхгүй.

- `forecasts/YYYY-MM-DD.json`: asof өдрийн хадгалсан таамаг (model хувилбар, сэдэв бүрийн h1–h3 Δ̂/pct/80% интервал/уншилт,
  `was_missing`, Anomaly, нөхцөл байдлын код, "үргэлжлэх/унтрах" дүгнэлт, сангийн хувилбар, Render-тэй харьцуулалт). Нэг удаа бичигдэнэ.
- `deltas/YYYY-MM-DD.csv`: тэр ажиллагаа Wikimedia-аас шинээр татсан түүхий мөрүүд (нэр = delta-ийн сүүлийн өдөр). Дараагийн ажиллагаа
  `main`-ийн `data/processed/` + эдгээрээс эхэлнэ.
- `attempts.jsonl`: оролдлого бүрийн цаг ба статус (`logged`, `already_logged`, `not_published`, `error`).
