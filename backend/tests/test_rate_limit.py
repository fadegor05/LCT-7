"""Тесты для SlidingWindowRateLimiter — скользящего лимита частоты запросов."""


class FakeClock:
    """Поддельные часы для детерминированного тестирования."""

    def __init__(self, initial_time: float = 0.0) -> None:
        """Инициализировать часы с начальным временем."""
        self.current_time = initial_time

    def __call__(self) -> float:
        """Вернуть текущее время."""
        return self.current_time

    def advance(self, seconds: float) -> None:
        """Продвинуть время на указанное количество секунд."""
        self.current_time += seconds


def test_limit_three_then_rejected() -> None:
    """Три хита разрешены, четвёртый отклонен."""
    from app.core.rate_limit import SlidingWindowRateLimiter

    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(limit=3, window_s=60.0, clock=clock)

    # Три хита разрешены
    assert limiter.hit("key1") is None
    assert limiter.hit("key1") is None
    assert limiter.hit("key1") is None

    # Четвёртый отклонен с положительным числом секунд
    wait_s = limiter.hit("key1")
    assert wait_s is not None
    assert 0 < wait_s <= 60


def test_after_wait_next_hit_allowed() -> None:
    """После ожидания возвращённого значения следующий хит разрешен."""
    from app.core.rate_limit import SlidingWindowRateLimiter

    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(limit=3, window_s=60.0, clock=clock)

    # Три хита разрешены
    assert limiter.hit("key1") is None
    assert limiter.hit("key1") is None
    assert limiter.hit("key1") is None

    # Четвёртый отклонен
    wait_s = limiter.hit("key1")
    assert wait_s is not None

    # Продвигаемся на возвращённое время + небольшой буфер
    clock.advance(wait_s + 0.01)

    # Теперь хит разрешен
    assert limiter.hit("key1") is None


def test_sliding_window_behavior() -> None:
    """Истинное скользящее окно: хиты в t=0,10,20 с окном 60 — в t=61 ровно один слот свободен."""
    from app.core.rate_limit import SlidingWindowRateLimiter

    clock = FakeClock(initial_time=0.0)
    limiter = SlidingWindowRateLimiter(limit=3, window_s=60.0, clock=clock)

    # t=0: первый хит
    assert limiter.hit("key1") is None
    clock.advance(10.0)

    # t=10: второй хит
    assert limiter.hit("key1") is None
    clock.advance(10.0)

    # t=20: третий хит
    assert limiter.hit("key1") is None
    clock.advance(10.0)

    # t=30: четвёртый отклонен (все три слота занимаются хитами в t=0,10,20)
    wait_s = limiter.hit("key1")
    assert wait_s is not None

    # t=61: первый хит (t=0) истекает, один слот свободен
    clock.advance(31.0)  # Теперь t=61
    assert limiter.hit("key1") is None


def test_keys_independent() -> None:
    """Разные ключи независимы."""
    from app.core.rate_limit import SlidingWindowRateLimiter

    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(limit=3, window_s=60.0, clock=clock)

    # Три хита для "a"
    assert limiter.hit("a") is None
    assert limiter.hit("a") is None
    assert limiter.hit("a") is None

    # Три хита для "b" должны быть разрешены
    assert limiter.hit("b") is None
    assert limiter.hit("b") is None
    assert limiter.hit("b") is None

    # Четвёртый для "b" отклонен
    assert limiter.hit("b") is not None

    # Четвёртый для "a" также отклонен
    assert limiter.hit("a") is not None


def test_rejected_hit_not_recorded() -> None:
    """Отклонённый хит не записывается."""
    from app.core.rate_limit import SlidingWindowRateLimiter

    clock = FakeClock(initial_time=0.0)
    limiter = SlidingWindowRateLimiter(limit=2, window_s=60.0, clock=clock)

    # Два хита разрешены в разные моменты времени
    assert limiter.hit("key1") is None  # t=0, _hits=[[0]]
    clock.advance(10.0)  # t=10
    assert limiter.hit("key1") is None  # t=10, _hits=[[0, 10]]

    # Третий отклонен
    wait_s = limiter.hit("key1")  # t=10, reject, wait=60-(10-0)=50
    assert wait_s is not None

    # Даже если сразу же попытаться снова, остаётся отклонен
    # (отклонённый хит не был записан)
    wait_s_2 = limiter.hit("key1")
    assert wait_s_2 is not None

    # После того как первый хит истечёт, новый хит будет разрешен
    clock.advance(wait_s + 0.01)  # t=60.01, первый хит (t=0) истекает
    assert limiter.hit("key1") is None  # Разрешен, _hits=[[10, 60.01]]

    # Но не второй, так как отклонённый не был записан
    # (второй хит уже в окне, поэтому следующий отклонен)
    wait_s_3 = limiter.hit("key1")
    assert wait_s_3 is not None


def test_limit_zero_rejects_all() -> None:
    """Лимит <= 0 отклоняет все хиты, но возвращает положительное время ожидания."""
    from app.core.rate_limit import SlidingWindowRateLimiter

    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(limit=0, window_s=60.0, clock=clock)

    # Все хиты отклонены
    wait_s = limiter.hit("key1")
    assert wait_s is not None
    assert wait_s > 0
    # Для лимита 0, время ожидания должно быть window_s
    assert wait_s == 60.0


def test_limit_negative_rejects_all() -> None:
    """Отрицательный лимит отклоняет все хиты."""
    from app.core.rate_limit import SlidingWindowRateLimiter

    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(limit=-1, window_s=60.0, clock=clock)

    # Все хиты отклонены
    wait_s = limiter.hit("key1")
    assert wait_s is not None
    assert wait_s > 0


def test_pruning_10000_keys() -> None:
    """После 10000 ключей, истёкших на окно, следующий хит оставляет 1 ключ."""
    from app.core.rate_limit import SlidingWindowRateLimiter

    clock = FakeClock(initial_time=0.0)
    limiter = SlidingWindowRateLimiter(limit=1, window_s=60.0, clock=clock)

    # Создаём 10000 различных ключей с одним хитом каждый
    for i in range(10000):
        assert limiter.hit(f"key{i}") is None

    # Все хиты в t=0, продвигаемся за пределы окна
    clock.advance(61.0)  # Теперь t=61

    # Делаем один новый хит
    assert limiter.hit("new_key") is None

    # Внутреннее хранилище должно содержать ровно 1 ключ
    assert len(limiter._hits) == 1
    assert "new_key" in limiter._hits
