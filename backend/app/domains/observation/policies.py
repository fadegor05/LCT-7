"""Чистые функции сведения наблюдений: агрегация, наблюдаемость, активность."""

import uuid
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.domains.observation.activity import (
    NO_SERIES,
    ActivityParams,
    MachineActivity,
    Shot,
    camera_activity,
    class_activity,
)
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
              - source_confidence — HIGH, если во всех date_sources нет выведенных
                источников ("stamp"/"filename"/"neighbours"), иначе MEDIUM (дата выведена
                сервисом, а не получена со снимком, см. architecture.md §7.3/§7.4).
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
        # HIGH если нет выведенных источников даты, иначе MEDIUM
        source_confidence = Confidence.HIGH
        if any(source in ("stamp", "filename", "neighbours") for source in date_sources):
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


@dataclass(frozen=True)
class CameraSeries:
    """Кадры одной камеры за день: имя и зона — для основания."""

    name: str
    zone: Sequence[Sequence[float]] | None
    shots: Sequence[Shot]
    zone_name: str | None = None


class ActivityPolicy:
    """Активность техники за день по сериям кадров каждой камеры (clean-mvp, D-018).

    По одному снимку работа не видна: «работает» ставится только по сдвигу машины между
    соседними кадрами одной камеры, «простаивает» — гипотеза для неподвижной машины вне
    зоны. Снимки без камеры или без времени серии не дают — по ним «неизвестно».
    """

    def __init__(self, params: ActivityParams) -> None:
        self._params = params

    def assess_day(
        self,
        series: Sequence[CameraSeries],
        present: Iterable[uuid.UUID],
    ) -> dict[uuid.UUID, MachineActivity]:
        """Итог по каждому типу техники за день.

        Args:
            series: кадры со временем каждой камеры за день.
            present: все типы техники, найденные за день (в том числе на снимках без серии).
        """
        machines: dict[uuid.UUID, list[MachineActivity]] = {}
        for cam in series:
            for m in camera_activity(
                cam.shots,
                zone=cam.zone,
                camera=cam.name,
                params=self._params,
                zone_name=cam.zone_name,
            ):
                machines.setdefault(m.equipment_type_id, []).append(m)
        result: dict[uuid.UUID, MachineActivity] = {}
        for kind in present:
            found = machines.get(kind)
            result[kind] = (
                class_activity(found)
                if found
                else MachineActivity(kind, Activity.UNKNOWN, NO_SERIES, None)
            )
        return result
