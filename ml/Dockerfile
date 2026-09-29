# Проверка ML-части в чистом окружении: то, что работает на машине разработчика,
# на сервере часто не заводится — не хватает системной библиотеки или шрифта.
#
# Образ намеренно на процессоре: GPU по ТЗ не обязателен, а 364 мс на кадр при
# съёмке раз в 20–30 минут дают запас в сотни камер на ядро.
# База 3.12: numpy 2.5 (нужен rapidocr для чтения штампа, LCT-13) собран только
# под Python 3.12+. Раньше стояла 3.11, потому что Docker Hub недоступен из сети
# разработки; теперь образ собирает GitHub Actions (.github/workflows/cd.yml).
FROM python:3.12-slim

# libGL и libglib нужны opencv; без них импорт падает на чистом slim-образе
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Отдельным слоем, чтобы не переустанавливать при каждой правке кода.
# Сборка +cpu: в образе GPU нет, а обычный torch тянет ~2 ГБ CUDA-зависимостей.
RUN pip install --no-cache-dir \
        torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir ultralytics==8.4.153 pillow==12.3.0 huggingface_hub         "fastapi>=0.115" "uvicorn[standard]>=0.30" python-multipart>=0.0.9 \
        opencv-python-headless==5.0.0.93 numpy==2.5.2 rapidocr-onnxruntime==1.2.3

COPY service/ /app/service/
COPY tools/ /app/tools/
COPY configs/ /app/configs/

# Веса не копируем в образ: 42 МБ и лицензия AGPL на них же. Монтируются томом.
ENV WEIGHTS=/weights/mocs_m_best.pt     PYTHONUNBUFFERED=1     YOLO_OFFLINE=1     YOLO_CONFIG_DIR=/tmp

EXPOSE 8000

# Проверка живости для оркестратора: /health модель не трогает и отвечает сразу.
# start-period 90 с — столько занимает загрузка и прогрев модели на процессоре.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3     CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4).status==200 else 1)"

CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
