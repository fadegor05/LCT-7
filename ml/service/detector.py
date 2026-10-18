"""Обёртка детектора для встраивания в бэкенд.

Скрипты в tools/ рассчитаны на запуск из командной строки: читают папку, пишут
JSON в файл. Бэкенду нужно другое — модель загружается один раз, дальше на вход
приходит кадр, на выход детекции. Этот модуль даёт такой интерфейс.

Формат выхода — тот же контракт, что у tools/detect_finetuned.py
(docs/CONTRACTS.md §1): bbox в долях кадра, порядок [x1, y1, x2, y2].
Это важно: дальше по цепочке идут site_state и match_schedule, которые
рассчитывают именно на него.

Использование:

    from service.detector import Detector
    det = Detector()                      # веса и порог берутся из конфига
    result = det.predict_path("frame.jpg")
    result = det.predict_bytes(data)      # для загрузки через HTTP
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

ML = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = ML / "weights" / "mocs_m_best.pt"
DEFAULT_IMGSZ = 960          # размер обучения; на другом качество падает
DEFAULT_CONF = 0.25          # рабочий порог, см. E12: подбор по классам не переносится
DEFAULT_IOU = 0.7
CONTRACT = "detect/v1"       # версия контракта для /meta


@dataclass
class Detector:
    """Загружает модель один раз и отдаёт детекции в формате контракта."""

    weights: Path = DEFAULT_WEIGHTS
    imgsz: int = DEFAULT_IMGSZ
    conf: float = DEFAULT_CONF
    iou: float = DEFAULT_IOU
    device: str | None = None       # None — выбрать автоматически
    _model: Any = field(default=None, init=False, repr=False)
    weights_sha256: str = field(default="", init=False, repr=False)

    def __post_init__(self) -> None:
        if not Path(self.weights).exists():
            raise FileNotFoundError(
                f"нет файла весов {self.weights}. Веса не хранятся в git "
                f"(великоваты): см. docs/MODEL_CARD.md, раздел «Где взять веса»")

        # Вычисляем SHA256 весов, читая по кускам
        sha256_hash = hashlib.sha256()
        with open(self.weights, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        self.weights_sha256 = sha256_hash.hexdigest()

        if self.device is None:
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"

    @property
    def model(self):
        """Ленивая загрузка: процесс бэкенда стартует быстро, модель — при первом кадре."""
        if self._model is None:
            from ultralytics import YOLO
            self._model = YOLO(str(self.weights))
        return self._model

    @property
    def model_id(self) -> str:
        """Идентификатор модели в формате stem@sha12."""
        return f"{Path(self.weights).stem}@{self.weights_sha256[:12]}"

    @property
    def class_names(self) -> list[str]:
        """Названия классов упорядоченные по id."""
        names_dict = self.model.names
        return [names_dict[i] for i in sorted(names_dict)]

    def warmup(self) -> None:
        """Прогрев: первый прогон вчетверо дольше из-за выделения памяти."""
        import numpy as np
        self.model.predict(np.zeros((self.imgsz, self.imgsz, 3), dtype="uint8"),
                           imgsz=self.imgsz, verbose=False, device=self.device)

    def _predict(self, source, name: str) -> dict:
        started = time.perf_counter()
        result = self.model.predict(source, imgsz=self.imgsz, conf=self.conf,
                                    iou=self.iou, device=self.device, verbose=False)[0]
        height, width = result.orig_shape
        detections = [
            {
                "class_raw": result.names[int(cls_id)],
                "class_ours": result.names[int(cls_id)],
                "conf": round(float(score), 3),
                "bbox": [round(float(v), 4) for v in box],
            }
            for cls_id, score, box in zip(result.boxes.cls.tolist(),
                                          result.boxes.conf.tolist(),
                                          result.boxes.xyxyn.tolist())
        ]
        # Сортируем детекции по уверенности в убывающем порядке
        detections.sort(key=lambda d: d["conf"], reverse=True)
        return {
            "model": self.model_id,
            "image": name,
            "width": int(width),
            "height": int(height),
            "speed_ms": {**result.speed, "total": round((time.perf_counter() - started) * 1000, 1)},
            "detections": detections,
        }

    def predict_path(self, path: str | Path) -> dict:
        return self._predict(str(path), Path(path).name)

    def predict_bytes(self, data: bytes, name: str = "upload") -> dict:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        return self._predict(img, name)

    def meta(self) -> dict:
        """Что за модель отвечает — для журнала и для отчёта пользователю."""
        card = ML / "docs" / "MODEL_CARD.md"
        return {
            "weights": Path(self.weights).name,
            "imgsz": self.imgsz,
            "conf": self.conf,
            "iou": self.iou,
            "device": self.device,
            "classes": len(self.model.names),
            "model_card": str(card) if card.exists() else None,
            "weights_sha256": self.weights_sha256,
            "model": self.model_id,
            "contract": CONTRACT,
            "class_names": self.class_names,
        }


# Время, которое знакогенератор камеры впечатал слева сверху (ml/stamp/).
# Порог — как у бэкенда (FRAMES__STAMP_MIN_CONFIDENCE, см. ml/stamp/eval.py).
CAMERA_MIN_CONFIDENCE = 0.9
# Включается переменной окружения STAMP_CAMERA_READER=1 (true/yes). По умолчанию выключено:
# точность на настоящих кадрах не проверена, а /stamp кормит даты фото в проде.


def camera_reader_enabled() -> bool:
    """Читается при каждом вызове, а не при импорте: тесты могут подменить окружение."""
    return os.environ.get("STAMP_CAMERA_READER", "").strip().lower() in ("1", "true", "yes")


@dataclass
class StampReader:
    """Ленивая загрузка RapidOCR: не грузить веса, пока штамп не нужен.

    Сначала — эталоны знаков камеры для известных разрешений (мс, без OCR).
    Если кадр такого разрешения не прочитан уверенно или разрешение неизвестно,
    работает прежний путь: OCR даты в углах кадра.
    """

    _ocr: Any = field(default=None, init=False, repr=False)
    _camera: Any = field(default=None, init=False, repr=False)

    @property
    def ocr(self):
        if self._ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr = RapidOCR()
        return self._ocr

    @property
    def camera_templates(self):
        if self._camera is None:
            from stamp.templates import load_all
            self._camera = load_all()
        return self._camera

    def warmup(self) -> None:
        import numpy as np
        from tools.read_date_stamp import read_stamp_array
        read_stamp_array(np.zeros((200, 200, 3), dtype="uint8"), self.ocr)

    def read_camera(self, img) -> dict | None:
        """Время камеры по эталонам; None — не прочитано уверенно, решает OCR."""
        import numpy as np
        from stamp.reader import read_gray
        gray = np.asarray(img.convert("L"), dtype=np.float32)
        out = read_gray(gray, self.camera_templates)
        if out is None:
            return None
        read, profile = out
        if read.captured_at is None or read.confidence < CAMERA_MIN_CONFIDENCE:
            return None
        return {"date": read.captured_at.date().isoformat(),
                "text": read.text, "roi": "camera", "profile": profile.name}

    def read_bytes(self, data: bytes) -> dict:
        from PIL import Image, ImageOps
        from tools.read_date_stamp import read_stamp_for_service
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        if camera_reader_enabled():
            camera = self.read_camera(img)
            if camera is not None:
                return camera
        arr = np.asarray(img.convert("RGB"))
        return read_stamp_for_service(arr, self.ocr)


def main() -> int:
    """Проверка обёртки без бэкенда: python -m service.detector <кадр>"""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("image", type=Path)
    ap.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    ap.add_argument("--conf", type=float, default=DEFAULT_CONF)
    args = ap.parse_args()

    det = Detector(weights=args.weights, conf=args.conf)
    print("модель:", json.dumps(det.meta(), ensure_ascii=False))
    out = det.predict_path(args.image)
    print(f"кадр {out['image']} {out['width']}x{out['height']}, "
          f"{len(out['detections'])} детекций, {out['speed_ms']['total']} мс")
    for d in out["detections"][:10]:
        print(f"   {d['class_ours']:<20}{d['conf']:.2f}  {d['bbox']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
