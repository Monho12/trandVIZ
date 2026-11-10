# Шуугиан — Hugging Face Docker Space (#9, ADR 0008).
#   local:  docker build -t shuugian . && docker run --rm -p 7860:7860 shuugian
#           -> http://127.0.0.1:7860   (offline: -e SHUUGIAN_REFRESH=0)
FROM python:3.13-slim

# lightgbm-д OpenMP хэрэгтэй
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# HF Space контейнерийг uid 1000-аар ажиллуулдаг: data/live/-д бичих эрхтэй байхын тулд ижил хэрэглэгч.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /home/user/app

COPY --chown=user requirements-app.txt .
RUN pip install --user -r requirements-app.txt

COPY --chown=user src/ src/
COPY --chown=user app/ app/
# data/processed/ = эхлэх cache (#8); сервер дутуу өдрүүдийг data/live/-д нэмж татна
COPY --chown=user data/ data/

EXPOSE 7860
# Нэг process: Server state + өдөр тутмын шинэчлэлтийн thread нэг л байх ёстой (--workers нэмэхгүй)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
