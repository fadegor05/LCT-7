"""Тесты для политик наблюдения: агрегация, наблюдаемость, активность."""

import uuid
from datetime import datetime

from app.domains.observation.activity import ActivityParams, Box, Shot
from app.domains.observation.models import Activity, Confidence, Observability
from app.domains.observation.policies import (
    ActivityPolicy,
    AggregationPolicy,
    CameraSeries,
    FrameEquipment,
    ObservabilityPolicy,
)


class TestAggregationPolicy:
    """Тесты AggregationPolicy.aggregate()."""

    def test_aggregation_policy_uses_max_not_sum(self):
        """DoD-критический тест: 5 кадров с одной машиной -> count_min=1, не 5.

        Один кадр одной машины, снятый с 5 разных точек, должен дать count_min=1.
        """
        equipment_id = uuid.uuid4()

        # 5 кадров, каждый с одной детекцией одного и того же типа техники
        frames = [
            [FrameEquipment(equipment_id, score=0.9)],
            [FrameEquipment(equipment_id, score=0.85)],
            [FrameEquipment(equipment_id, score=0.88)],
            [FrameEquipment(equipment_id, score=0.92)],
            [FrameEquipment(equipment_id, score=0.87)],
        ]
        date_sources = [None, None, None, None, None]

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        # count_min должен быть 1 (максимум на одном кадре), не 5
        assert equipment_id in result
        assert result[equipment_id].count_min == 1

    def test_aggregation_two_frames_two_each_gives_count_min_two(self):
        """2 кадра, каждый с 2 детекциями одного типа -> count_min=2, не 4."""
        equipment_id = uuid.uuid4()

        frames = [
            [FrameEquipment(equipment_id, score=0.8), FrameEquipment(equipment_id, score=0.75)],
            [FrameEquipment(equipment_id, score=0.85), FrameEquipment(equipment_id, score=0.82)],
        ]
        date_sources = [None, None]

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        assert equipment_id in result
        assert result[equipment_id].count_min == 2

    def test_aggregation_different_types_different_frames(self):
        """Разные типы техники на разных кадрах -> каждый тип с правильным max."""
        type_a = uuid.uuid4()
        type_b = uuid.uuid4()

        frames = [
            [FrameEquipment(type_a, score=0.9), FrameEquipment(type_a, score=0.85)],
            [FrameEquipment(type_b, score=0.8)],
            [FrameEquipment(type_a, score=0.88)],
            [FrameEquipment(type_b, score=0.75), FrameEquipment(type_b, score=0.78)],
        ]
        date_sources = [None, None, None, None]

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        assert result[type_a].count_min == 2
        assert result[type_b].count_min == 2

    def test_aggregation_stamp_source_caps_confidence_at_medium(self):
        """date_sources содержит "stamp" -> confidence не выше MEDIUM даже при высоком score."""
        equipment_id = uuid.uuid4()

        frames = [[FrameEquipment(equipment_id, score=0.95)]]
        date_sources = ["stamp"]  # Низкий уровень доверия к источнику

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        assert result[equipment_id].confidence == Confidence.MEDIUM

    def test_aggregation_neighbours_source_caps_confidence_at_medium(self):
        """date_sources содержит "neighbours" -> confidence не выше MEDIUM."""
        equipment_id = uuid.uuid4()

        frames = [[FrameEquipment(equipment_id, score=0.95)]]
        date_sources = ["neighbours"]

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        assert result[equipment_id].confidence == Confidence.MEDIUM

    def test_aggregation_filename_source_caps_confidence_at_medium(self):
        """date_sources содержит "filename" -> confidence не выше MEDIUM (bug-reports/005)."""
        equipment_id = uuid.uuid4()

        frames = [[FrameEquipment(equipment_id, score=0.95)]]
        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, ["filename"])

        assert result[equipment_id].confidence == Confidence.MEDIUM

    def test_aggregation_high_score_high_source_gives_high_confidence(self):
        """High score + good source -> Confidence.HIGH."""
        equipment_id = uuid.uuid4()

        frames = [[FrameEquipment(equipment_id, score=0.9)]]
        date_sources = [None]  # Нет штампа/соседей -> HIGH source confidence

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        assert result[equipment_id].confidence == Confidence.HIGH

    def test_aggregation_medium_score_gives_medium_confidence(self):
        """Score в диапазоне MEDIUM -> Confidence.MEDIUM."""
        equipment_id = uuid.uuid4()

        frames = [[FrameEquipment(equipment_id, score=0.6)]]
        date_sources = [None]

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        assert result[equipment_id].confidence == Confidence.MEDIUM

    def test_aggregation_low_score_gives_low_confidence(self):
        """Score < min_score_medium -> Confidence.LOW."""
        equipment_id = uuid.uuid4()

        frames = [[FrameEquipment(equipment_id, score=0.3)]]
        date_sources = [None]

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        assert result[equipment_id].confidence == Confidence.LOW

    def test_aggregation_type_with_zero_detections_absent_from_result(self):
        """Тип техники, не обнаруженный ни на одном кадре, отсутствует в результате."""
        type_detected = uuid.uuid4()
        type_not_detected = uuid.uuid4()

        frames = [
            [FrameEquipment(type_detected, score=0.9)],
            [],  # Кадр без детекций
        ]
        date_sources = [None, None]

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        assert type_detected in result
        assert type_not_detected not in result

    def test_aggregation_empty_frames_returns_empty_dict(self):
        """Пустой список кадров -> пустой результат."""
        frames: list[list[FrameEquipment]] = []
        date_sources: list[str | None] = []

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        assert result == {}

    def test_aggregation_frames_with_empty_frames_list(self):
        """Список кадров, содержащий пустые frame'ы -> результат без типов из пустых."""
        type_a = uuid.uuid4()

        frames = [
            [FrameEquipment(type_a, score=0.9)],
            [],
            [FrameEquipment(type_a, score=0.85)],
        ]
        date_sources = [None, None, None]

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        assert type_a in result
        assert result[type_a].count_min == 1

    def test_aggregation_score_confidence_from_max_count_frame_not_global_best(self):
        """Score confidence должна быть от кадра с max count, не от глобально лучшего.

        Frame A: 1 детекция типа X с score=0.95 (глобально лучший score)
        Frame B: 3 детекции типа X с score=0.30 каждая (max count = 3)

        Результат:
        - count_min=3 (из frame B)
        - score_confidence должна быть LOW (0.30 < min_score_medium=0.4),
          а не HIGH (0.95 >= min_score_high=0.7)
        """
        equipment_id = uuid.uuid4()

        # Frame A: 1 детекция с high score
        frame_a = [FrameEquipment(equipment_id, score=0.95)]
        # Frame B: 3 детекции с low score
        frame_b = [
            FrameEquipment(equipment_id, score=0.30),
            FrameEquipment(equipment_id, score=0.30),
            FrameEquipment(equipment_id, score=0.30),
        ]

        frames = [frame_a, frame_b]
        date_sources = [None, None]

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        # count_min должен быть 3 (max count из frame B)
        assert result[equipment_id].count_min == 3
        # score_confidence должна быть LOW, потому что score из frame B (max count frame)
        # составляет 0.30, что < min_score_medium=0.4
        assert result[equipment_id].confidence == Confidence.LOW

    def test_aggregation_score_confidence_with_tied_max_count(self):
        """При равных max count на разных кадрах, используется лучший score из tied.

        Frame A: 2 детекции типа X с score=0.5 каждая (max = 2)
        Frame B: 2 детекции типа X с score=0.65 каждая (tie на max = 2)

        Результат:
        - count_min=2
        - score_confidence от лучшего из tied: 0.65 (> 0.5 из A),
          что >= min_score_medium=0.4 но < min_score_high=0.7 -> MEDIUM
        """
        equipment_id = uuid.uuid4()

        frame_a = [
            FrameEquipment(equipment_id, score=0.5),
            FrameEquipment(equipment_id, score=0.5),
        ]
        frame_b = [
            FrameEquipment(equipment_id, score=0.65),
            FrameEquipment(equipment_id, score=0.65),
        ]

        frames = [frame_a, frame_b]
        date_sources = [None, None]

        policy = AggregationPolicy(min_score_high=0.7, min_score_medium=0.4)
        result = policy.aggregate(frames, date_sources)

        assert result[equipment_id].count_min == 2
        # score_confidence от лучшего из tied: 0.65 >= 0.4 и < 0.7 -> MEDIUM
        assert result[equipment_id].confidence == Confidence.MEDIUM


class TestObservabilityPolicy:
    """Тесты ObservabilityPolicy.assess()."""

    def test_observability_high_threshold_met(self):
        """photo_count >= min_photos_high -> (HIGH, None)."""
        policy = ObservabilityPolicy(min_photos_medium=1, min_photos_high=3)

        obs, notes = policy.assess(3)
        assert obs == Observability.HIGH
        assert notes is None

        obs, notes = policy.assess(5)
        assert obs == Observability.HIGH
        assert notes is None

    def test_observability_medium_threshold_met(self):
        """photo_count >= min_photos_medium -> (MEDIUM, message)."""
        policy = ObservabilityPolicy(min_photos_medium=1, min_photos_high=3)

        obs, notes = policy.assess(1)
        assert obs == Observability.MEDIUM
        assert "недостаточно кадров для высокой наблюдаемости: 1" in notes

        obs, notes = policy.assess(2)
        assert obs == Observability.MEDIUM
        assert "недостаточно кадров для высокой наблюдаемости: 2" in notes

    def test_observability_low_threshold_not_met(self):
        """photo_count < min_photos_medium -> (LOW, message)."""
        policy = ObservabilityPolicy(min_photos_medium=1, min_photos_high=3)

        obs, notes = policy.assess(0)
        assert obs == Observability.LOW
        assert "мало кадров за дату: 0, вывод по объекту делать нельзя" in notes

    def test_observability_boundary_values(self):
        """Граничные значения для разных настроек."""
        policy = ObservabilityPolicy(min_photos_medium=2, min_photos_high=5)

        # Ниже MEDIUM
        obs, notes = policy.assess(0)
        assert obs == Observability.LOW

        obs, notes = policy.assess(1)
        assert obs == Observability.LOW

        # На уровне MEDIUM
        obs, notes = policy.assess(2)
        assert obs == Observability.MEDIUM

        obs, notes = policy.assess(3)
        assert obs == Observability.MEDIUM

        obs, notes = policy.assess(4)
        assert obs == Observability.MEDIUM

        # На уровне HIGH
        obs, notes = policy.assess(5)
        assert obs == Observability.HIGH

        obs, notes = policy.assess(10)
        assert obs == Observability.HIGH

    def test_observability_notes_text_exact_message(self):
        """Проверяем точный текст сообщений."""
        policy = ObservabilityPolicy(min_photos_medium=2, min_photos_high=5)

        obs, notes = policy.assess(0)
        assert notes == "мало кадров за дату: 0, вывод по объекту делать нельзя"

        obs, notes = policy.assess(3)
        assert notes == "недостаточно кадров для высокой наблюдаемости: 3"

        obs, notes = policy.assess(5)
        assert notes is None


class TestActivityPolicy:
    """Активность по серии кадров одной камеры за день (clean-mvp, D-018)."""

    EXC = uuid.uuid4()
    ZONE = [[0.0, 0.0], [0.5, 0.0], [0.5, 1.0], [0.0, 1.0]]  # левая половина кадра

    @staticmethod
    def _shot(minute: int, *boxes: tuple[uuid.UUID, list[float]]) -> Shot:
        return Shot(datetime(2026, 9, 9, 10, minute), tuple(Box(k, b) for k, b in boxes))

    def _day(self, *shots: Shot, zone=None, zone_name=None, present=None):
        policy = ActivityPolicy(ActivityParams())
        series = [CameraSeries("Север", zone, shots, zone_name=zone_name)]
        return policy.assess_day(series, present or [self.EXC])[self.EXC]

    def test_single_shot_is_unknown_not_works(self):
        """По одному снимку работа не видна — главное отличие от прежнего правила."""
        got = self._day(self._shot(0, (self.EXC, [0.1, 0.1, 0.2, 0.2])))
        assert got.activity is Activity.UNKNOWN
        assert "один кадр" in got.basis
        assert "не задана" in got.basis

    def test_moved_between_adjacent_shots_is_works(self):
        got = self._day(
            self._shot(0, (self.EXC, [0.1, 0.1, 0.2, 0.2])),
            self._shot(5, (self.EXC, [0.16, 0.1, 0.26, 0.2])),  # сдвиг 0.6 размера рамки
        )
        assert got.activity is Activity.WORKS
        assert got.basis.startswith("Движение: машина сместилась между 10:00 и 10:05")

    def test_same_minute_pair_shows_seconds(self):
        policy = ActivityPolicy(ActivityParams())
        shots = [
            Shot(datetime(2026, 9, 9, 19, 0, 5), (Box(self.EXC, [0.1, 0.1, 0.2, 0.2]),)),
            Shot(datetime(2026, 9, 9, 19, 0, 40), (Box(self.EXC, [0.16, 0.1, 0.26, 0.2]),)),
        ]
        got = policy.assess_day([CameraSeries("Север", None, shots)], [self.EXC])[self.EXC]
        assert got.basis.startswith("Движение: машина сместилась между 19:00:05 и 19:00:40")

    def test_long_gap_does_not_pair(self):
        """За разрыв больше 10 минут машина успеет уехать и вернуться — пары нет."""
        got = self._day(
            self._shot(0, (self.EXC, [0.1, 0.1, 0.2, 0.2])),
            self._shot(30, (self.EXC, [0.16, 0.1, 0.26, 0.2])),
        )
        assert got.activity is Activity.UNKNOWN

    def test_still_series_out_of_zone_is_idle_hypothesis(self):
        box = (self.EXC, [0.7, 0.1, 0.8, 0.2])
        got = self._day(*(self._shot(m, box) for m in (0, 5, 10, 15)), zone=self.ZONE)
        assert got.activity is Activity.IDLE
        assert got.basis.startswith("Гипотеза. Движение: нет на 4 кадрах подряд (10:00–10:15)")
        assert got.basis.endswith("Зона: вне зоны")

    def test_still_series_in_zone_stays_unknown(self):
        box = (self.EXC, [0.1, 0.1, 0.2, 0.2])
        got = self._day(*(self._shot(m, box) for m in (0, 5, 10, 15)), zone=self.ZONE)
        assert got.activity is Activity.UNKNOWN
        assert got.basis.endswith("Зона: внутри зоны")

    def test_still_series_out_of_zone_names_zone_in_basis(self):
        box = (self.EXC, [0.7, 0.1, 0.8, 0.2])
        got = self._day(
            *(self._shot(m, box) for m in (0, 5, 10, 15)), zone=self.ZONE, zone_name="Въезд"
        )
        assert got.activity is Activity.IDLE
        assert got.basis.endswith("Зона «Въезд»: вне зоны")

    def test_still_series_in_zone_names_zone_in_basis(self):
        box = (self.EXC, [0.1, 0.1, 0.2, 0.2])
        got = self._day(
            *(self._shot(m, box) for m in (0, 5, 10, 15)), zone=self.ZONE, zone_name="Въезд"
        )
        assert got.activity is Activity.UNKNOWN
        assert got.basis.endswith("Зона «Въезд»: внутри зоны")

    def test_zone_name_without_zone_keeps_not_set_text(self):
        """Название есть, зоны нет — текст «не задана» прежний, название в нём не нужно."""
        got = self._day(self._shot(0, (self.EXC, [0.1, 0.1, 0.2, 0.2])), zone_name="Въезд")
        assert "Зона: у камеры «Север» не задана" in got.basis
        assert "Въезд" not in got.basis

    def test_camera_moved_pair_is_ignored(self):
        """Все три машины сдвинулись разом — подвинули камеру, а не машины поехали."""
        boxes = [[0.1, 0.1, 0.2, 0.2], [0.4, 0.4, 0.5, 0.5], [0.7, 0.7, 0.8, 0.8]]
        first = self._shot(0, *((self.EXC, b) for b in boxes))
        moved = self._shot(5, *((self.EXC, [b[0] + 0.06, b[1], b[2] + 0.06, b[3]]) for b in boxes))
        assert self._day(first, moved).activity is Activity.UNKNOWN

    def test_type_without_series_is_unknown(self):
        other = uuid.uuid4()
        policy = ActivityPolicy(ActivityParams())
        got = policy.assess_day([], [other])[other]
        assert got.activity is Activity.UNKNOWN
        assert "нет серии кадров" in got.basis

    def test_works_wins_over_idle_across_cameras(self):
        policy = ActivityPolicy(ActivityParams())
        still = (self.EXC, [0.7, 0.1, 0.8, 0.2])
        idle_cam = CameraSeries("Юг", self.ZONE, [self._shot(m, still) for m in (0, 5, 10, 15)])
        works_cam = CameraSeries(
            "Север",
            None,
            [
                self._shot(0, (self.EXC, [0.1, 0.1, 0.2, 0.2])),
                self._shot(5, (self.EXC, [0.16, 0.1, 0.26, 0.2])),
            ],
        )
        got = policy.assess_day([idle_cam, works_cam], [self.EXC])[self.EXC]
        assert got.activity is Activity.WORKS
