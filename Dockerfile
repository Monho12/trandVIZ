# check=skip=JSONArgsRecommended
# Шуугиан — Docker image (#9, ADR 0008, 0010: хамгаалалт дээр local, 0011: Render free).
#   local:  docker build -t shuugian . && docker run --rm -p 7860:7860 shuugian
#           -> http://127.0.0.1:7860   (offline: -e SHUUGIAN_REFRESH=0)
FROM python:3.13-slim

# apt алхам алга: libgomp1 зөвхөн lightgbm-д хэрэгтэй байсан, серверт CatBoost л бий (ADR 0011).

# root биш хэрэглэгч (uid 1000); data/live/-д бичих эрхтэй.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ARROW_DEFAULT_MEMORY_POOL=system \
    MALLOC_ARENA_MAX=2
# Сүүлийн 2: санах ойн оргил (ADR 0012, Render 512 MB). pyarrow-ийн mimalloc pool parquet уншсаны дараа санах ойг
# процесст барьдаг; glibc-ийн arena-г 2 болгож thread бүрийн тусдаа heap-ийг хязгаарлана. Үр дүнд нөлөөлөхгүй.
WORKDIR /home/user/app

COPY --chown=user requirements-app.txt .
RUN pip install --user -r requirements-app.txt

COPY --chown=user src/ src/
COPY --chown=user app/ app/
# data/processed/ = эхлэх cache (#8); сервер дутуу өдрүүдийг data/live/-д нэмж татна
COPY --chown=user data/ data/

EXPOSE 7860
# Нэг process: Server state + өдөр тутмын шинэчлэлтийн thread нэг л байх ёстой (--workers нэмэхгүй)
# Shell хэлбэр (JSON биш тул дээрх check=skip): Render.com порт-оо $PORT-оор өгнө, local-д 7860 (ADR 0011). exec: uvicorn PID 1 болж SIGTERM-ийг авна.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}
