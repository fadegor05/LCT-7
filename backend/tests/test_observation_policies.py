"""Тесты для политик наблюдения: агрегация, наблюдаемость, активность."""

import uuid

from app.domains.observation.models import Activity, Confidence, Observability
from app.domains.observation.policies import (
    ActivityPolicy,
    AggregationPolicy,
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
    """Тесты ActivityPolicy.assess()."""

    def test_activity_previous_none_returns_unknown(self):
        """previous_bboxes=None -> UNKNOWN."""
        policy = ActivityPolicy(movement_threshold=0.05)

        current = [[0.0, 0.0, 0.1, 0.1]]
        result = policy.assess(current, None)

        assert result == Activity.UNKNOWN

    def test_activity_previous_empty_returns_unknown(self):
        """previous_bboxes=[] -> UNKNOWN."""
        policy = ActivityPolicy(movement_threshold=0.05)

        current = [[0.0, 0.0, 0.1, 0.1]]
        previous: list[list[float]] = []
        result = policy.assess(current, previous)

        assert result == Activity.UNKNOWN

    def test_activity_current_empty_returns_unknown(self):
        """current_bboxes=[] -> UNKNOWN даже если previous не пуст."""
        policy = ActivityPolicy(movement_threshold=0.05)

        current: list[list[float]] = []
        previous = [[0.0, 0.0, 0.1, 0.1]]
        result = policy.assess(current, previous)

        assert result == Activity.UNKNOWN

    def test_activity_large_shift_below_threshold_returns_works(self):
        """Большой сдвиг >= threshold -> WORKS."""
        policy = ActivityPolicy(movement_threshold=0.05)

        # Центр текущего: (0.45, 0.45)
        current = [[0.4, 0.4, 0.5, 0.5]]
        # Центр предыдущего: (0.05, 0.05)
        previous = [[0.0, 0.0, 0.1, 0.1]]

        # Расстояние: sqrt((0.45-0.05)^2 + (0.45-0.05)^2) = sqrt(0.32) ≈ 0.566 >> 0.05
        result = policy.assess(current, previous)

        assert result == Activity.WORKS

    def test_activity_small_shift_below_threshold_returns_unknown(self):
        """Маленький сдвиг < threshold -> UNKNOWN."""
        policy = ActivityPolicy(movement_threshold=0.05)

        # Центр текущего: (0.55, 0.55)
        current = [[0.5, 0.5, 0.6, 0.6]]
        # Центр предыдущего: (0.55, 0.55)
        previous = [[0.5, 0.5, 0.6, 0.6]]

        # Расстояние: 0
        result = policy.assess(current, previous)

        assert result == Activity.UNKNOWN

    def test_activity_multiple_bboxes_averaging(self):
        """Множество bbox'ов в одной стороне -> усреднение центров."""
        policy = ActivityPolicy(movement_threshold=0.05)

        # Два bbox'а: центры (0.25, 0.25) и (0.35, 0.35), в среднем (0.3, 0.3)
        current = [[0.2, 0.2, 0.3, 0.3], [0.3, 0.3, 0.4, 0.4]]
        # Один bbox: центр (0.05, 0.05)
        previous = [[0.0, 0.0, 0.1, 0.1]]

        # Расстояние: sqrt((0.3-0.05)^2 + (0.3-0.05)^2) = sqrt(0.125) ≈ 0.354 >> 0.05
        result = policy.assess(current, previous)

        assert result == Activity.WORKS

    def test_activity_threshold_boundary(self):
        """Расстояние ровно на границе threshold."""
        policy = ActivityPolicy(movement_threshold=0.1)

        # Центр текущего: (0.15, 0.15)
        current = [[0.1, 0.1, 0.2, 0.2]]
        # Центр предыдущего: (0.05, 0.05)
        previous = [[0.0, 0.0, 0.1, 0.1]]

        # Расстояние: sqrt((0.15-0.05)^2 + (0.15-0.05)^2) = sqrt(0.02) ≈ 0.1414...
        # Это >= 0.1, поэтому должно быть WORKS
        result = policy.assess(current, previous)

        assert result == Activity.WORKS

    def test_activity_never_returns_idle(self):
        """Политика никогда не возвращает IDLE для источника фото."""
        policy = ActivityPolicy(movement_threshold=0.05)

        # Проверяем, что даже при нулевом movement_threshold не получится IDLE
        # (хотя это не очень реалистично, но убеждаемся в коде)

        # Легкий сдвиг
        current = [[0.15, 0.15, 0.25, 0.25]]
        previous = [[0.1, 0.1, 0.2, 0.2]]

        result = policy.assess(current, previous)
        assert result in (Activity.WORKS, Activity.UNKNOWN)
        assert result != Activity.IDLE

    def test_activity_three_previous_bboxes_averaging(self):
        """Три предыдущих bbox'а с усреднением."""
        policy = ActivityPolicy(movement_threshold=0.05)

        # Текущий: один bbox с центром (0.5, 0.5)
        current = [[0.45, 0.45, 0.55, 0.55]]

        # Три предыдущих: центры (0.0, 0.0), (0.1, 0.1), (0.2, 0.2)
        # Средний центр: (0.1, 0.1)
        previous = [
            [0.0, 0.0, 0.0, 0.0],
            [0.05, 0.05, 0.15, 0.15],
            [0.15, 0.15, 0.25, 0.25],
        ]

        # Расстояние: sqrt((0.5-0.1)^2 + (0.5-0.1)^2) = sqrt(0.32) ≈ 0.566 >> 0.05
        result = policy.assess(current, previous)

        assert result == Activity.WORKS
