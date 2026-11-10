# Шуугиан — Дэлхий юуг шуугиж байна?

Wikipedia-ийн өдөр тутмын хандалтаар дэлхийн анхаарлыг хэмжиж, **ирэх 3 өдрийн**
сонирхлыг gradient boosting-оор (LightGBM / XGBoost / CatBoost-оос valid-аар сонгосон) таамагладаг Data Mining төсөл.

## Хурдан эхлэх (laptop / гэрийн PC аль алин дээр)

```bash
git clone https://github.com/Monho12/trandVIZ.git
cd trandVIZ
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
jupyter lab
```

Ажлын дэг: суух бүрдээ **`git pull`**, дуусахдаа **`git push`**.

### Вэбийг өөрийн компьютер дээр ажиллуулах

```bash
uvicorn app.main:app --reload
```

Браузерт **http://127.0.0.1:8000** нээнэ. Сервер эхлэхдээ `app/model/`-ийн model-ийг ачаалж, хүсэлт бүрт таамаг гаргана
(ADR 0008). Өдөрт нэг удаа Wikimedia-аас дутуу сүүлийн өдрүүдийг татаж `data/live/`-д хадгална.
Интернэтгүй ажиллуулах бол `SHUUGIAN_REFRESH=0`. Model амьд ажиллаж байгааг **http://127.0.0.1:8000/api/model** харуулна.

### Docker (ижил орчинг давтах)

```bash
docker build -t shuugian .
docker run --rm -p 7860:7860 shuugian
```

Браузерт **http://127.0.0.1:7860**. Image-д `app/model/` болон эхлэх cache `data/processed/` орсон байна.
Image зөвхөн серверт хэрэгтэй сангуудыг суулгана (`requirements-app.txt`).

### Онлайн (Render.com)

**Сайт:** https://trandviz.onrender.com — `/api/model` нь ажиллаж буй model-ийг харуулна.
Render-ийн үнэгүй Docker Web Service (512 MB, ADR 0011): серверт зөвхөн CatBoost ачаалагдана.
15 минут хүсэлтгүй бол унтдаг тул эхний нээлт ~1 минут удаж болно. Порт нь Render-ийн `$PORT` (local-д 7860).

### Хамгаалалт дээр

Үндсэн нь дээрх Render-ийн линк (5 минутын өмнө нээж сэрээнэ). Нөөц нь **local** (ADR 0010).
Хамгаалалтын өмнө `uvicorn app.main:app`-ийг ажиллуулж http://127.0.0.1:8000 болон `/api/model`-ийг нээж шалгана.
Интернэт найдваргүй бол `SHUUGIAN_REFRESH=0` (Windows `cmd`: `set SHUUGIAN_REFRESH=0`): сервер repo доторх өгөгдөл дээр ажиллаж,
asof хуучин бол шар анхааруулга харуулна. Нөөц: `docker run -p 7860:7860 shuugian` (http://127.0.0.1:7860).

## Бүтэц

| Хавтас | Юу байгаа |
|---|---|
| `data/articles.csv` | Сонгосон ~150 сэдэв, 10 ангилалтай |
| `data/viral_articles.csv` | 2021 оноос хойшхи ~150 вирал сэдэв |
| `data/processed/` | Цэвэрлэсэн өгөгдөл (`.parquet`) — git-д хадгалагдана |
| `data/raw/` | Түүхий cache — git-д **орохгүй** |
| `src/` | Python код (өгөгдөл татах, feature, model) |
| `notebooks/` | Алхам алхмаар тайлбартай notebook-ууд |
| `app/` | FastAPI backend + вэб |
| `docs/` | Хамгаалалтын хуудас, слайд |

## Төлөвлөгөө

Дэлгэрэнгүй: [`docs/PLAN.md`](docs/PLAN.md) (өдөр бүрийн заавар), шийдвэрүүд: [`docs/adr/`](docs/adr/), нэр томьёо: [`CONTEXT.md`](CONTEXT.md).

| Өдөр | Алхам | Notebook |
|---|---|---|
| Бя 11/07 | Өгөгдөл татах | `01_data_collection.ipynb` |
| Ня 11/08 | Цэвэрлэх + EDA | `02_cleaning_eda.ipynb` |
| Да 11/09 | Feature engineering + selection | `03_features.ipynb` |
| Мя 11/10 | 3 алгоритм + Optuna + overfit + test үнэлгээ | `04_model.ipynb` |
| Лх 11/11 | Model-ийг сайтын ард → local Docker → слайд | `app/` |
| Пү 11/12 | Нөөц өдөр, хамгаалалт | — |

## Өгөгдлийн эх сурвалж

[Wikimedia Pageviews API](https://wikimedia.org/api/rest_v1/) — зөвхөн хүний
уншилт (`agent=user`). Wikimedia сангийн мэдээлснээр Wikipedia-ийн (бүх хэл) хүний уншилт 2025 оны сүүлийн хэдэн сард
2024 оны мөн саруудтай харьцуулахад ~8% буурсан ([Diff, 2025-10-17](https://diff.wikimedia.org/2025/10/17/new-user-trends-on-wikipedia/)).
Манай өгөгдөлд ч мөн адил: англи Wikipedia-ийн өдрийн дундаж уншилт 2026 оны 1/1–11/6-нд 2024 оны мөн үеэс ~14% бага.
Тиймээс бид уншилтын тоог биш, **анхаарлын хувь**-ийг (нийтлэлийн уншилт ÷ нийт уншилт) таамаглана.
