# Шуугиан — Дэлхий юуг шуугиж байна?

Wikipedia-ийн өдөр тутмын хандалтаар дэлхийн анхаарлыг хэмжиж, **ирэх 3 өдрийн**
сонирхлыг LightGBM-ээр таамагладаг Data Mining төсөл.

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

| Өдөр | Алхам | Notebook |
|---|---|---|
| Бя 11/07 | Өгөгдөл татах | `01_data_collection.ipynb` |
| Ня 11/08 | Цэвэрлэх + EDA | `02_cleaning_eda.ipynb` |
| Да 11/09 | Feature engineering + selection | `03_features.ipynb` |
| Мя 11/10 | LightGBM + Optuna + overfit шалгалт | `04_model.ipynb` |
| Лх 11/11 | Вэб + deploy + слайд | `app/` |
| Пү 11/12 | Нөөц өдөр, хамгаалалт | — |

## Өгөгдлийн эх сурвалж

[Wikimedia Pageviews API](https://wikimedia.org/api/rest_v1/) — зөвхөн хүний
хандалт (`agent=user`). Wikipedia-ийн нийт хүний хандалт 2025 онд ~8% буурсан
тул бид хандалтын тоог биш, **анхаарлын хувь**-ийг (нийтлэлийн хандалт ÷ нийт
хандалт) таамаглана.
