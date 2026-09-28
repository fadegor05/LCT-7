"""запасной детектор для запуска без весов: отдаёт заранее посчитанные детекции.

Веса модели лежат в приватном репозитории: они производны от снимков
организаторов, а те публичными быть не должны (D-005). Из-за этого посторонний —
в том числе жюри — не может просто склонировать репозиторий и поднять сервис:
он упрётся в отсутствующий файл весов.

Этот модуль закрывает разрыв. Если весов нет, но задан `DEMO_DETECTIONS`,
сервис поднимается и на каждый кадр отвечает **заранее посчитанными**
детекциями из выгрузки, которая в репозитории есть. Вся цепочка после
детектора — свод по площадке, сопоставление с планом, отчёт, выгрузка — работает
на настоящих числах.

**Это не имитация работы модели.** Каждый ответ помечен `"source": "demo"`, в
`meta()` стоит `"mode": "demo"`, а на неизвестный кадр модуль отвечает пустым
списком детекций, а не выдумывает рамки. Выдать демо-ответ за живой прогон
нельзя ни случайно, ни намеренно.

Как включить:

    export DEMO_DETECTIONS=data/processed/detections_mocs_m.json
    uvicorn service.app:app

Соответствие кадру ищется по имени файла. Прислали кадр, которого в выгрузке
нет, — вернётся пустой список и пометка `matched: false`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ML = Path(__file__).resolve().parents[1]


@dataclass
class DemoDetector:
    """Повторяет интерфейс `Detector`, но берёт детекции из файла."""

    # Путь к выгрузке либо уже прочитанные данные в том же формате. Второе
    # нужно тестам: заводить файл ради проверки поведения незачем.
    source: Path | dict
    imgsz: int = 960
    conf: float = 0.25
    iou: float = 0.7
    device: str = "demo"
    _by_name: dict[str, dict] = field(default_factory=dict, init=False, repr=False)
    _name: str = field(default="", init=False, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.source, dict):
            data, self._name = self.source, "переданные данные"
        else:
            path = Path(self.source)
            if not path.is_absolute():
                path = ML / path
            if not path.exists():
                raise FileNotFoundError(f"нет выгрузки детекций {path} для демо-режима")
            data = json.loads(path.read_text(encoding="utf-8"))
            self._name = path.name
        self._by_name = {im["image"]: im for im in data.get("images", [])}

    def warmup(self) -> None:
        """Греть нечего: файл уже прочитан."""

    def meta(self) -> dict:
        return {
            "mode": "demo",
            "weights": None,
            "source": self._name,
            "frames_available": len(self._by_name),
            "imgsz": self.imgsz,
            "conf": self.conf,
            "device": "demo",
            "note": ("Демо-режим: детекции взяты из готовой выгрузки, модель не "
                     "запускалась. Нужен для запуска без приватных весов."),
        }

    def _answer(self, name: str, data: bytes | None = None) -> dict:
        started = time.perf_counter()
        found = self._by_name.get(name)
        detections = [dict(d, source="demo") for d in (found or {}).get("detections", [])
                      if d.get("conf", 1.0) >= self.conf]
        return {
            "image": name,
            "width": int((found or {}).get("width", 0)),
            "height": int((found or {}).get("height", 0)),
            "speed_ms": {"total": round((time.perf_counter() - started) * 1000, 1)},
            "detections": detections,
            "mode": "demo",
            "matched": found is not None,
        }

    def predict_path(self, path: str | Path) -> dict:
        return self._answer(Path(path).name)

    def predict_bytes(self, data: bytes, name: str = "upload") -> dict:
        return self._answer(name, data)


def build(weights: Path, demo_source: str | None) -> Any:
    """Настоящий детектор, если веса есть; иначе демо, если он разрешён.

    Порядок именно такой: наличие весов всегда важнее. Демо-режим не должен
    незаметно подменить живую модель, если её просто забыли прогреть.
    """
    from service.detector import Detector

    if Path(weights).exists():
        return Detector(weights=Path(weights))
    if demo_source:
        return DemoDetector(source=Path(demo_source))
    raise FileNotFoundError(
        f"нет файла весов {weights}. Либо скачайте их "
        f"(python tools/fetch_weights.py), либо задайте DEMO_DETECTIONS "
        f"для запуска без модели — см. service/demo_detector.py")
