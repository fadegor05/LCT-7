"""Чистые функции сведения наблюдений: агрегация, наблюдаемость, активность."""

import math
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from app.domains.observation.models import Activity, Confidence, Observability


@dataclass(frozen=True)
class FrameEquipment:
    """Одна детекция одного кадра, минимум для агрегации."""

    equipment_type_id: uuid.UUID
    score: float


@dataclass(frozen=True)
class AggregatedEquipment:
    """Результат агрегации по одному типу техники за дату."""

    count_min: int
    confidence: Confidence


class AggregationPolicy:
    """Максимум по кадрам (не сумма) + уверенность по score детекции и источнику даты."""

    def __init__(self, min_score_high: float, min_score_medium: float) -> None:
        self._min_score_high = min_score_high
        self._min_score_medium = min_score_medium

    def aggregate(
        self,
        frames: Sequence[Sequence[FrameEquipment]],
        date_sources: Sequence[str | None],
    ) -> dict[uuid.UUID, AggregatedEquipment]:
        """Агрегировать детекции по кадрам за дату.

        Args:
            frames: одна Sequence[FrameEquipment] на кадр этой даты.
            date_sources: date_source всех кадров этой даты, для потолка confidence.

        Returns:
            Словарь {equipment_type_id: AggregatedEquipment}.

        Логика:
            - count_min(type) = max(Counter(детекций этого типа на одном кадре)) по всем кадрам.
              Никогда не сумма.
            - confidence(type) = min(score_confidence, source_confidence):
              - score_confidence — по лучшему score этого типа среди кадров, давших максимум
                count_min (кадры, на которых зафиксирован максимальный счёт этого типа).
                Если несколько кадров имеют count == max для типа (tie), используем лучший
                score из этих tied кадров. >= min_score_high -> HIGH, >= min_score_medium
                -> MEDIUM, иначе LOW.
              - source_confidence — HIGH, если во всех date_sources нет "stamp"/"neighbours",
                иначе MEDIUM (штамп/соседи — источник хуже, см. architecture.md §7.3/§7.4).
            - Тип техники без детекций ни на одном кадре в результат не попадает.
        """
        # Для каждого типа техники отслеживаем: (max_count, best_score_from_max_frame)
        max_count_per_type: dict[uuid.UUID, int] = {}
        # best_score_from_max_count_frame: только score из кадра(ов), давших max count
        score_per_type: dict[uuid.UUID, float] = {}

        # Обходим все кадры
        for frame in frames:
            # Считаем детекции по типам в этом кадре
            counter = Counter(eq.equipment_type_id for eq in frame)

            # Обновляем max count и score for each equipment type in this frame
            for equipment in frame:
                etype_id = equipment.equipment_type_id
                score = equipment.score
                frame_count = counter[etype_id]

                current_max = max_count_per_type.get(etype_id, 0)

                if frame_count > current_max:
                    # Это новый максимум для этого типа; заменяем данные
                    max_count_per_type[etype_id] = frame_count
                    score_per_type[etype_id] = score
                elif frame_count == current_max:
                    # Tie: берём лучший score из двух tied кадров (этого и предыдущего)
                    current_best = score_per_type.get(etype_id, -1.0)
                    if score > current_best:
                        score_per_type[etype_id] = score
                # Если frame_count < current_max, игнорируем score этого кадра

        # Определяем source_confidence
        # HIGH если нет "stamp"/"neighbours", иначе MEDIUM
        source_confidence = Confidence.HIGH
        if any(source in ("stamp", "neighbours") for source in date_sources):
            source_confidence = Confidence.MEDIUM

        # Строим результат
        result: dict[uuid.UUID, AggregatedEquipment] = {}

        for equipment_type_id, count_min in max_count_per_type.items():
            best_score = score_per_type[equipment_type_id]

            # Определяем score_confidence
            if best_score >= self._min_score_high:
                score_confidence = Confidence.HIGH
            elif best_score >= self._min_score_medium:
                score_confidence = Confidence.MEDIUM
            else:
                score_confidence = Confidence.LOW

            # Финальная confidence — минимум из двух
            confidence = self._min_confidence(score_confidence, source_confidence)

            result[equipment_type_id] = AggregatedEquipment(
                count_min=count_min, confidence=confidence
            )

        return result

    @staticmethod
    def _min_confidence(c1: Confidence, c2: Confidence) -> Confidence:
        """Вернуть минимальную (худшую) confidence из двух."""
        order = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}
        return c1 if order[c1] <= order[c2] else c2


class ObservabilityPolicy:
    """Наблюдаемость по числу кадров за дату (без камер/зон — MVP-упрощение)."""

    def __init__(self, min_photos_medium: int, min_photos_high: int) -> None:
        self._min_photos_medium = min_photos_medium
        self._min_photos_high = min_photos_high

    def assess(self, photo_count: int) -> tuple[Observability, str | None]:
        """Оценить наблюдаемость по числу фотографий.

        Args:
            photo_count: Количество фотографий за дату.

        Returns:
            Кортеж (observability, notes):
            - photo_count >= min_photos_high -> (HIGH, None).
            - photo_count >= min_photos_medium -> (MEDIUM, message).
            - иначе -> (LOW, message).
        """
        if photo_count >= self._min_photos_high:
            return (Observability.HIGH, None)
        elif photo_count >= self._min_photos_medium:
            msg = f"недостаточно кадров для высокой наблюдаемости: {photo_count}"
            return (Observability.MEDIUM, msg)
        else:
            msg = f"мало кадров за дату: {photo_count}, вывод по объекту делать нельзя"
            return (Observability.LOW, msg)


class ActivityPolicy:
    """Активность по сдвигу среднего центра bbox между соседними датами (без зон камер)."""

    def __init__(self, movement_threshold: float) -> None:
        self._movement_threshold = movement_threshold

    def assess(
        self,
        current_bboxes: Sequence[Sequence[float]],
        previous_bboxes: Sequence[Sequence[float]] | None,
    ) -> Activity:
        """Оценить активность техники по смещению центра bbox.

        Args:
            current_bboxes: Текущие bbox'ы в формате [x1, y1, x2, y2] в долях кадра.
            previous_bboxes: Предыдущие bbox'ы (None, пусто или список).

        Returns:
            Activity.WORKS если смещение >= movement_threshold,
            Activity.UNKNOWN иначе.

        Логика:
            - Нет previous_bboxes (None или пусто) или current_bboxes пуст -> UNKNOWN.
            - Иначе: center(bboxes) = среднее ((x1+x2)/2, (y1+y2)/2) по всем bbox в списке.
            - euclidean(center(current), center(previous)) >= movement_threshold -> WORKS,
              иначе UNKNOWN.
            - Activity.IDLE на источнике "фото" не выводится вообще.
        """
        # Проверяем граничные условия
        if previous_bboxes is None or len(previous_bboxes) == 0 or len(current_bboxes) == 0:
            return Activity.UNKNOWN

        # Вычисляем центры
        current_center = self._compute_center(current_bboxes)
        previous_center = self._compute_center(previous_bboxes)

        # Вычисляем евклидово расстояние
        distance = math.sqrt(
            (current_center[0] - previous_center[0]) ** 2
            + (current_center[1] - previous_center[1]) ** 2
        )

        # Сравниваем с порогом
        if distance >= self._movement_threshold:
            return Activity.WORKS
        else:
            return Activity.UNKNOWN

    @staticmethod
    def _compute_center(bboxes: Sequence[Sequence[float]]) -> tuple[float, float]:
        """Вычислить средний центр всех bbox'ов.

        Args:
            bboxes: Список [x1, y1, x2, y2] в долях кадра.

        Returns:
            Кортеж (cx, cy) среднего центра.
        """
        centers = []
        for bbox in bboxes:
            x1, y1, x2, y2 = bbox
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            centers.append((cx, cy))

        if not centers:
            return (0.0, 0.0)

        avg_cx = sum(c[0] for c in centers) / len(centers)
        avg_cy = sum(c[1] for c in centers) / len(centers)

        return (avg_cx, avg_cy)
