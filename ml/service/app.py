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

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from service.detector import (  # noqa: F401
    DEFAULT_CONF,
    DEFAULT_IMGSZ,
    DEFAULT_WEIGHTS,
    Detector,
    StampReader,
)
from service.export import to_csv, to_html, to_xlsx
from service.pipeline import build_report, summary

logger = logging.getLogger(__name__)

MAX_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 20 * 1024 * 1024))
_detector: Detector | None = None
_stamp_reader: StampReader | None = None


class Detection(BaseModel):
    class_raw: str = Field(description="что ответила модель")
    class_ours: str = Field(description="класс нашей таксономии")
    conf: float
    bbox: list[float] = Field(description="доли кадра, [x1, y1, x2, y2]")
    source: str | None = Field(
        None, description="detected — распознано, registered — из реестра, demo — из выгрузки")


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
    # Демо-режим обязан быть отличим от живого прогона. Поля необязательные:
    # при работе с настоящими весами их просто нет.
    mode: str | None = Field(None, description="«demo», если модель не запускалась")
    matched: bool | None = Field(
        None, description="в демо-режиме: нашёлся ли кадр в готовой выгрузке")


class StampResponse(BaseModel):
    date: str | None
    text: str | None
    roi: str | None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Модель грузится и прогревается на старте: первый запрос не должен ждать
    секунды на выделение памяти."""
    global _detector
    from service.demo_detector import build

    weights = Path(os.environ.get("WEIGHTS") or DEFAULT_WEIGHTS)
    _detector = build(weights, os.environ.get("DEMO_DETECTIONS"))
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


def _ask_report_module():
    """Ленивый импорт модуля ask_report из tools/.

    Используется как /meta, так и /ask для получения конфигурации провайдера.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import ask_report  # noqa: E402
    return ask_report


@app.get("/health", summary="Жив ли сервис")
def health() -> dict:
    return {"status": "ok", "model_loaded": _detector is not None}


@app.get("/meta", summary="Чем именно отвечает сервис")
def meta() -> dict:
    """Версия весов и пороги — чтобы в журнале бэкенда было видно, какая модель
    дала ответ. Без этого через месяц не разобраться, откуда взялась детекция.
    Также показывает, доступен ли ассистент (статус LLM_*)."""
    ask_report = _ask_report_module()
    cfg = ask_report.llm_config()
    return {**detector().meta(), "stamp": True, "assistant": cfg is not None}


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


@app.post("/report/export", summary="Отчёт файлом: CSV, XLSX или HTML для печати")
def report_export(req: ReportRequest,
                  fmt: str = Query("xlsx", pattern="^(csv|xlsx|html)$"),
                  what: str = Query("stages", pattern="^(stages|alerts)$")) -> Response:
    """Заказчик — департамент: выводы попадают в документооборот, а JSON туда не
    приложишь. HTML открывается в браузере и сохраняется в PDF без отдельной
    библиотеки в образе.

    `what` действует только для CSV: в XLSX оба листа, в HTML обе таблицы.
    """
    if not req.observations or not req.schedule:
        raise HTTPException(400, "нужны и наблюдения, и календарный план")
    result = build_report([o.model_dump() for o in req.observations],
                          [s.model_dump() for s in req.schedule], conf=req.conf)
    stamp = datetime.now().strftime("%Y%m%d")
    if fmt == "csv":
        body, media, name = to_csv(result, what), "text/csv; charset=utf-8", f"report_{what}_{stamp}.csv"
    elif fmt == "xlsx":
        body, media, name = (to_xlsx(result),
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             f"report_{stamp}.xlsx")
    else:
        return HTMLResponse(to_html(result))
    return Response(content=body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


class AskRequest(BaseModel):
    """Вопрос по готовому отчёту."""

    question: str = Field(min_length=3, max_length=500)
    report: dict = Field(description="отчёт, полученный из POST /report")
    site_id: str | None = Field(None, description="ограничить одной площадкой")


@app.post("/ask", summary="Вопрос по отчёту на естественном языке")
def ask_about_report(req: AskRequest) -> dict:
    """Пересказ отчёта языковой моделью — с проверкой каждого числа.

    Решение проекта (D-020): языковая модель **не порождает выводы**, она
    пересказывает готовые. Выводы по-прежнему делают правила, и каждое число в
    них прослеживается до нормы и снимка.

    Риск пересказа — подставленное число. Поэтому ответ проверяется по двум
    уровням: числа, которых в отчёте нет вовсе, и числа, которые в отчёте есть,
    но относятся к другой площадке. Не прошло — в ответе стоит `verified:
    false`, и подавать его как факт нельзя.

    Проверяются числа, а не смысл: верное число, отнесённое не к тому этапу,
    проверка не увидит. Это записано и здесь, и в ответе.
    """
    ask_report = _ask_report_module()

    cfg = ask_report.llm_config()
    if not cfg:
        raise HTTPException(503, "языковая модель не настроена: нет LLM_BASE_URL, "
                                 "LLM_API_KEY или LLM_MODEL")

    data = ask_report.compact(req.report, req.site_id)
    if not data["sites"]:
        raise HTTPException(400, "в отчёте нет запрошенных площадок")

    prompt = (f"Отчёт:\n{json.dumps(data, ensure_ascii=False)}\n\n"
              f"Вопрос: {req.question}")
    try:
        answer = ask_report.ask(prompt, cfg.base_url, cfg.api_key, cfg.model,
                                timeout=120, system=ask_report.SYSTEM)
    except Exception as exc:
        logger.warning("/ask: вызов LLM не удался: %s", ask_report.describe_llm_error(exc))
        raise HTTPException(504, f"языковая модель не ответила: {ask_report.describe_llm_error(exc)}") from exc

    missing = ask_report.unverified(answer, ask_report.collect_numbers(data))
    by_site = ask_report.numbers_by_site(data)
    wrong_site = ask_report.misattributed(answer, by_site)
    return {
        "answer": answer.strip(),
        "verified": not (missing or wrong_site),
        "numbers_not_in_report": missing,
        "numbers_of_other_site": wrong_site,
        "limits": ask_report.limits_for(answer, by_site),
    }


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
