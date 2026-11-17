# Handoff: trandVIZ (Шуугиан): давтамжийн скрипт (#54)

Дараагийн session **[#54](https://github.com/Monho12/trandVIZ/issues/54)**-өөс эхэлнэ: ADR 0019–0021, 0026-ийн тоог дахин гаргах скрипт.
Энэ бол prototype-ийн урьдчилсан нөхцөл. UI/UX grill (2026-11-17) дууссан, шийдвэрүүд бүгд repo-д бий.

## Эх сурвалж (энд давтахгүй, уншина уу)

- **#54-ийн бие**: 14 тоо, тодорхойлолт (дүгнэлт = таамагласан pct (h3) ≤ −10%; бодит үр дүнг h3 өдрөөр), гаралт, acceptance criteria. Энэ бол үндсэн spec.
- **PR [#55](https://github.com/Monho12/trandVIZ/pull/55)** (branch `claude/confident-faraday-rcm37r` → `main`): ADR 0023–0028 ба бусад ADR-ийн нэмэлт. Майк GitHub дээр өөрөө merge хийнэ.
  Merge болоогүй бол энэ branch-аас эхэл. **Merge болсны дараа #45-д `ready-for-agent` шошгыг буцааж тавина** (`docs/PLAN.md`-ийн W6a мөр).
- `docs/PLAN.md`: "Trend Intelligence — ажлын дараалал" (#54-ийн мөр), "UI grill-ийн шийдвэрүүд", **"Скриптийн дараа шийдэх"** (Майкаас асуух 2 асуулт),
  "Prototype-ийн процесс", "Theme-д мэдрэмтгий сонголтууд".
- `CONTEXT.md` = glossary (`CLAUDE.md` `GLOSSARY.md` гэж бичсэн ч тийм файл байхгүй). Шинэ: Хүчтэй өсөлтийн таамаг, Үргэлжлэх / Унтрах, Үндсэн хувь ("ердийн үед").
- `docs/ui-tests/tsesnii-ner-expectation-test.md`: Майк prototype шатанд өөрөө хийнэ.

## Скриптийн ажлын анхааруулга (artifact-д бичигдээгүй)

- **Тоо зөрвөл ADR-ийг засаад Майкт шууд хэл.** Ялангуяа #12 (Буцалтын naive дүрэм): model naive "ердийн түвшин рүү буцна" дүрмээс бараг илүү биш гарвал
  энэ нь дипломд чухал бөгөөд нүүрний "Сэргэх төлөвтэй" хэсэг хэвээр үлдэх эсэхийг өөрчилнө (PLAN "Скриптийн дараа шийдэх").
  ADR 0020-д "уналтын гүн" дүрэм 41.9% (CatBoost 58.9%) байгаа нь "30.1% нь хэт зөөлөн суурь" гэсэн Майкийн сэжигтэй таарч байна.
- **#13-ийн X%-ийг track record-ын үр дүнг харахаас өмнө** тогтоож ADR 0016-д огноотой бич (pre-registration). Дарааллыг алдагдуулахгүй.
- Өмнөх session-ий скрипт repo-д ч, git түүхэнд ч байхгүй. "69.5% + 30.5% = 100%" тул хоёр тоо нэг хэмжүүрээс гарсан нь л тодорхой. h3 эсэх нь баримтгүй.
- Мөрүүд: `src/calibrate.py: valid_frame` ((в)-гүй valid, хэмжигдэх). Test-ийг ашиглахгүй (ADR 0002).
- `clean.parquet` / `features.parquet` gitignore-д. `python -m src.clean && python -m src.features`-ээр дахин үүсгэнэ.
- Энэ cloud орчинд **pytest суугаагүй** байсан. `pip install -r requirements.txt` (эсвэл serving-д `requirements-app.txt`) хэрэгтэй.
- `/api/*` өөрчлөгдөхгүй байх ёстой (`tests/test_golden.py`).

## Орчны анхааруулга

- Cloud session-д GitHub GraphQL хаалттай. Issue / PR-т GitHub MCP tool-ууд ашигла (`docs/agents/issue-tracker.md`-ийн REST заавар нь `gh` CLI-д).
- `trandviz.onrender.com` энэ cloud орчны сүлжээний бодлогоор **хаалттай** байсан. ADR 0027-ийн cold start-ийн хэмжилт хийгдээгүй (prototype шатанд).
- UI хэмжилт: `index.html` нь `/static/...` абсолют замтай. file://-аас нээвэл CSS ачаалагдахгүй тул хэмжилт буруу гарна
  (энэ session нэг удаа алдсан). `app/` дотроос `python3 -m http.server`, эсвэл `uvicorn app.main:app` (`SHUUGIAN_REFRESH=0`) ашигла.
- `/to-tickets`, `/handoff`, `/grill-with-docs` бол зөвхөн хэрэглэгч дуудах skill.

## Майкийн ажлын хэв маяг

- Монголоор ярина, техникийн нэр томьёог англиар үлдээнэ. Нэг удаад **нэг** асуулт, санал болгосон хариултаа хамт өгнө.
- Кодоос олж болох баримтыг Майкаас асуухгүй. Тоо бүрт эх сурвалж, null finding-ийг шударгаар хэлнэ. Буруу хэмжилт гарвал шууд засаж хэлнэ.
- Шийдвэр бүрийг `CONTEXT.md` / `docs/adr/`-д тэр дор нь бичиж commit + push хийнэ.
- UI: зөвхөн `impeccable`, `emil-design-eng`, `dataviz`, `prototype`. `frontend-design`, `design-taste-frontend` хориотой (`CLAUDE.md`, ADR 0025).

## Suggested skills

- `tdd`: #54-ийг test-first (дүгнэлт, h3 үр дүн, мөчлөгийн өсөлтийг хасах, үндсэн хувь).
- `domain-modeling`: тоо зөрвөл ADR ба `CONTEXT.md`-г шинэчлэх.
- `code-review`: #54-ийн PR-ийн өмнө.
- `pr`: PR-ийн бие.
- Дараагийн шат: `prototype` (+ `impeccable`, `emil-design-eng`, `dataviz`), `docs/PLAN.md`-ийн "Prototype-ийн процесс"-ийн дагуу.
