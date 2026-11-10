# Render.com-ийн үнэгүй Docker Web Service; серверт зөвхөн CatBoost

(Майкийн шийдвэр, 2026-11-10.) ADR 0010-ийг нөхнө: хамгаалалт дээр local хэвээр **нөөц** болно, онлайн линкийг
Render.com-ийн үнэгүй (512 MB санах ой) Docker Web Service дээр нэмнэ. Model сайтын ард ажиллах загвар (ADR 0008) хэвээр.

## Яагаад

- **Hugging Face:** шинэ Docker / CPU Basic Space PRO төлбөртэй болсон (ADR 0010).
- **Azure for Students:** сургуулийн и-мэйлийг танихгүй байсан тул эрх авч чадаагүй.
- **Render free:** Docker Web Service-ийг үнэгүй ажиллуулна, гэхдээ санах ой **512 MB**. Өмнөх image 512 MB-д
  `/api/model` хүсэлтийн үед OOM-оор унасан (доорх хэмжилт). Тиймээс серверт хэрэггүй зүйлийг хассан:
  - Сервер зөвхөн сонгосон **CatBoost**-ийг ачаална (`meta.json: algo`). `src/train.py` нь lightgbm, xgboost, optuna,
    catboost-ийг модулийн дээд талд биш, ашиглах функц дотор нь import хийнэ. `train.load()` зөвхөн `algo`-гийн санг ачаална.
    `requirements-app.txt`-ээс lightgbm, xgboost-cpu, optuna-г хассан. Сургалт, notebook (`requirements.txt`) өөрчлөгдөөгүй.
    `tests/test_deploy.py` нь `app.main` import хийгээд model ачаалахад эдгээр сан `sys.modules`-д орохгүйг шалгана.
  - `libgomp1` (apt) зөвхөн lightgbm-д хэрэгтэй байсан тул Dockerfile-аас хассан (CatBoost-ийн `.so` түүнийг шаарддаггүй).
  - `/api/model`-ийн "Яаж хийсэн бэ?" доторх `naive_mae_by_period` ~590k мөр дээр "train"/"valid" мөрийн массив
    2 удаа үүсгэж ~80 MiB оргил гаргадаг байсан. int8 кодоор сольсон (ижил үр дүн: 0.1912 / 0.1826), оргил ~9 MiB.
- LightGBM / XGBoost-ийн харьцуулалт "Загвар" хуудсанд `meta.json`-оос static-аар харагдсаар байна (model файл хэрэггүй).

## Хэмжилт (`docker run --memory=512m --memory-swap=512m`, cgroup-ийн оргил, page cache орно)

| | Өмнө | Дараа |
|---|---|---|
| Image (`docker images`) | 1.62 GB | 1.52 GB |
| (а) эхлэх | 381 MiB | 376 MiB |
| (б) `/api/trending` | 434 MiB | 428 MiB |
| (б) `/api/map` | 405 MiB | 398 MiB |
| (б) `/api/topic/ChatGPT` | 423 MiB | 403 MiB |
| (б) `/api/model` | **OOM (унасан)** | 478 MiB |
| (в) Wikimedia-ийн шинэчлэлт (3 өдөр) | 503 MiB | 484 MiB |

Процессын RSS-ийн оргил (VmHWM): эхлэх 483 → 463 MiB, `/api/model` OOM → 554 MiB (хуваалцсан `.so` хуудас cgroup-т
бүрэн тооцогдоогүй тул cgroup-ийн тооноос их). (в)-г sandbox-оос wikimedia.org хаалттай байсан тул ижил хэлбэрийн
хуурамч API-аар хэмжсэн (281 сэдэв + alias, 3 өдөр, шинэ snapshot барих).

## Эрсдэл

- **Нөөц бага:** оргил ~480–500 MiB, 512 MB-аас ~15–30 MiB л зай. Өгөгдөл өсөх тусам (өдөр бүр мөр нэмэгдэнэ) зай
  багасна. OOM болвол Render контейнерийг дахин эхлүүлнэ (image доторх `data/processed/`-ээс эхэлнэ).
- **15 минут хүсэлтгүй бол унтдаг:** дараагийн хүсэлтэд сэрэхэд ~1 минут орчим. Хамгаалалтаас 5 минутын өмнө сэрээнэ.
- **Диск түр зуурынх:** `data/live/` дахин эхлэх, deploy бүрд устна. Сервер эхлэх бүртээ image-ийн
  `data/processed/`-ээс дутуу өдрүүдийг дахин татна (хэдхэн минут, тэр хооронд asof-ийн шар анхааруулга гарна).
- **Нэг process** (`--workers` нэмэхгүй): Server state + шинэчлэлтийн thread нэг л байх ёстой; санах ойд ч тохирно.
- `CMD` нь shell хэлбэр: `exec uvicorn ... --port ${PORT:-7860}` (Render `$PORT` өгнө, local-д 7860).

## Local нөөц

Render унтсан, OOM болсон эсвэл интернэт муу бол ADR 0010-ийн local хэвээр: `uvicorn app.main:app`
(http://127.0.0.1:8000) эсвэл `docker run -p 7860:7860 shuugian`, интернэтгүй бол `SHUUGIAN_REFRESH=0`.
