---
title: Шуугиан
emoji: 📈
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Wikipedia-ийн анхаарлын 3 өдрийн таамаг (gradient boosting)
---

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

### Docker (Hugging Face Space-тэй яг ижил image)

```bash
docker build -t shuugian .
docker run --rm -p 7860:7860 shuugian
```

Браузерт **http://127.0.0.1:7860**. Image-д `app/model/` болон эхлэх cache `data/processed/` орсон байна.
Image зөвхөн серверт хэрэгтэй сангуудыг суулгана (`requirements-app.txt`).

### Hugging Face Space руу байршуулах

Эхлээд HF бүртгэл, Space (`SDK = Docker`), token-ийг **өөрөө** үүсгэнэ: [`docs/PLAN.md`](docs/PLAN.md) → "Hugging Face тохиргоо".
Token-ийг repo, `.env`, notebook, commit, чат хаана ч бичихгүй.

```bash
huggingface-cli login          # "Add token as git credential?" гэхэд Y
git remote add space https://huggingface.co/spaces/<нэр>/shuugian
bash scripts/deploy_space.sh   # HEAD-ийг Space руу
```

Энгийн `git push space main` ажиллахгүй: HF нь 10 MB-аас том болон binary файлыг (`app/model/*.cbm`, `*.parquet`, фонт)
LFS-гүй хүлээж авдаггүй. Скрипт HEAD-ийн нэг commit-тэй хуулбарыг LFS-тэйгээр Space руу push хийнэ. GitHub-ийн түүх өөрчлөгдөхгүй.
Дараа нь Space-ийн **Logs** tab-аас build-ийг харж, `https://<нэр>-shuugian.hf.space/api/model` нээгдэж байгааг шалгана.

> **Хамгаалалтын өмнө:** үнэгүй Space 48 цаг хүсэлтгүй бол унтдаг, сэрэхэд 30+ секунд болдог.
> Хамгаалалтаас **~5 минутын өмнө** Space-ийг нээж сэрээнэ. Нөөц болгож local дээр `uvicorn app.main:app`
> эсвэл `docker run -p 7860:7860 shuugian`-ийг бэлэн байлгана. Space дахин эхлэх бүрд `data/live/` арилж,
> сервер `data/processed/`-оос хойших дутуу өдрүүдийг дахин татна (ердөө хэдэн секунд).

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
| Лх 11/11 | Model-ийг сайтын ард → local Docker → HF Space → слайд | `app/` |
| Пү 11/12 | Нөөц өдөр, хамгаалалт | — |

## Өгөгдлийн эх сурвалж

[Wikimedia Pageviews API](https://wikimedia.org/api/rest_v1/) — зөвхөн хүний
хандалт (`agent=user`). Wikipedia-ийн нийт хүний хандалт 2025 онд ~8% буурсан
тул бид хандалтын тоог биш, **анхаарлын хувь**-ийг (нийтлэлийн хандалт ÷ нийт
хандалт) таамаглана.
