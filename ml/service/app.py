"""HTTP-сервис детекции: тонкая обёртка над service/detector.py.

Зачем отдельный сервис, а не библиотека внутри бэкенда: модель держит в памяти
около 500 МБ и грузится секунды, а бэкенд перезапускается часто. Отдельный
процесс переживает перезапуски бэкенда и масштабируется независимо.

Формат ответа — контракт `docs/CONTRACTS.md` §1, тот же, что у CLI-прогона:
bbox в долях кадра, порядок [x1, y1, x2, y2]. Дальше по цепочке идут
site_state.py и match_schedule.py, которые рассчитывают именно на него.

Запуск:
    uvicorn service.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from service.detector import DEFAULT_CONF, DEFAULT_IMGSZ, Detector, StampReader
from service.pipeline import build_report, summary

MAX_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 20 * 1024 * 1024))
_detector: Detector | None = None
_stamp_reader: StampReader | None = None


class Detection(BaseModel):
    class_raw: str = Field(description="что ответила модель")
    class_ours: str = Field(description="класс нашей таксономии")
    conf: float
    bbox: list[float] = Field(description="доли кадра, [x1, y1, x2, y2]")


class Observation(BaseModel):
    """Кадр с привязкой: детекции плюс площадка и дата."""

    image: str
    site_id: str | None = Field(None, description="без неё кадр в анализ не попадёт")
    date: str | None = Field(None, description="ISO-дата съёмки; без неё кадр в анализ не попадёт")
    width: int = 0
    height: int = 0
    detections: list[Detection] = []


class ScheduleRow(BaseModel):
    site_id: str
    stage_code: str
    stage_name: str = ""
    planned_start: str
    planned_end: str
    note: str = ""


class ReportRequest(BaseModel):
    observations: list[Observation]
    schedule: list[ScheduleRow]
    conf: float = Field(DEFAULT_CONF, ge=0.0, le=1.0,
                        description="порог уверенности при подсчёте техники")


class FrameResult(BaseModel):
    model: str
    image: str
    width: int
    height: int
    speed_ms: dict[str, float]
    detections: list[Detection]


class StampResponse(BaseModel):
    date: str | None
    text: str | None
    roi: str | None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Модель грузится и прогревается на старте: первый запрос не должен ждать
    секунды на выделение памяти."""
    global _detector
    weights = os.environ.get("WEIGHTS")
    _detector = Detector(weights=Path(weights)) if weights else Detector()
    _detector.warmup()
    yield
    _detector = None


app = FastAPI(title="ЛЦТ-7: детектор строительной техники",
              description=__doc__, version="1.0", lifespan=lifespan)


def detector() -> Detector:
    if _detector is None:                      # до завершения lifespan
        raise HTTPException(503, "модель ещё не загружена")
    return _detector


def stamp_reader() -> StampReader:
    global _stamp_reader
    if _stamp_reader is None:
        _stamp_reader = StampReader()
    return _stamp_reader


@app.get("/health", summary="Жив ли сервис")
def health() -> dict:
    return {"status": "ok", "model_loaded": _detector is not None}


@app.get("/meta", summary="Чем именно отвечает сервис")
def meta() -> dict:
    """Версия весов и пороги — чтобы в журнале бэкенда было видно, какая модель
    дала ответ. Без этого через месяц не разобраться, откуда взялась детекция."""
    return {**detector().meta(), "stamp": True}


@app.post("/report", summary="Статусы этапов и алерты по площадкам")
def report(req: ReportRequest) -> dict:
    """Вторая половина цепочки: детекции сводятся по паре «площадка и дата» и
    сопоставляются с календарным планом.

    Кадры без площадки или даты в анализ не попадают: без даты нельзя сказать,
    отстаёт этап или нет. Они не теряются молча — счётчик в `meta` и алерт
    `unusable_data` по площадке (Q&A 13:01).
    """
    if not req.observations:
        raise HTTPException(400, "нет наблюдений")
    if not req.schedule:
        raise HTTPException(400, "нет календарного плана: не с чем сравнивать")
    try:
        result = build_report([o.model_dump() for o in req.observations],
                              [s.model_dump() for s in req.schedule],
                              conf=req.conf)
    except Exception as exc:
        raise HTTPException(422, f"не удалось построить отчёт: {exc}") from exc
    return {**result, "summary": summary(result)}


@app.post("/detect", response_model=FrameResult, summary="Детекции по одному кадру")
async def detect(file: UploadFile = File(description="снимок площадки")) -> FrameResult:
    data = await file.read()
    if not data:
        raise HTTPException(400, "пустой файл")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"файл больше {MAX_BYTES // 1048576} МБ")
    try:
        result = detector().predict_bytes(data, name=file.filename or "upload")
    except HTTPException:                      # пробросить HTTPException как есть
        raise
    except Exception as exc:                   # битый файл, неизвестный формат
        raise HTTPException(422, f"не удалось обработать кадр: {exc}") from exc
    return FrameResult(**result)


@app.post("/stamp", response_model=StampResponse, summary="Дата, впечатанная в кадр")
async def stamp(file: UploadFile = File(description="снимок площадки")) -> StampResponse:
    data = await file.read()
    if not data:
        raise HTTPException(400, "пустой файл")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"файл больше {MAX_BYTES // 1048576} МБ")
    try:
        result = stamp_reader().read_bytes(data)
    except Exception as exc:
        raise HTTPException(422, f"не удалось обработать кадр: {exc}") from exc
    return StampResponse(**result)
