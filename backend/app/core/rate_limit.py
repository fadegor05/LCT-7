"""Скользящий лимит частоты запросов (in-memory sliding window rate limiter).

Детерминированная реализация с инъектируемыми часами для тестирования.
"""

import time
from collections import deque


class SlidingWindowRateLimiter:
    """Скользящее окно для ограничения частоты обращений к дорогостоящему ресурсу.

    Хранит временные метки хитов (попыток) для каждого ключа в deque.
    На каждый запрос проверяет, сколько хитов уложилось в окно window_s,
    и принимает или отклоняет новый хит.
    Отклонённый хит не записывается.
    Память ограничивается через периодическую чистку истёкших ключей.
    """

    def __init__(self, limit: int, window_s: float = 60.0, clock=time.monotonic) -> None:
        """Инициализировать лимитер.

        Args:
            limit: Максимальное количество хитов за окно.
                   limit <= 0 отклоняет каждый хит, время ожидания = window_s.
            window_s: Длина скользящего окна в секундах.
            clock: Функция, возвращающая текущее время (по умолчанию time.monotonic).
        """
        self.limit = limit
        self.window_s = window_s
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._last_global_sweep = clock()

    def hit(self, key: str) -> float | None:
        """Записать попытку обращения к ресурсу по ключу.

        Проверяет, разрешена ли новая попытка в рамках лимита.
        На каждый вызов чистит истёкшие хиты для текущего ключа.
        Периодически чистит глобальное хранилище от пустых ключей.

        Args:
            key: Идентификатор сущности (e.g., владелец сайта).

        Returns:
            None, если попытка разрешена (записана в хранилище).
            float > 0, иначе: количество секунд до истечения самого старого хита в окне.
                     Отклонённая попытка в хранилище не записывается.
        """
        now = self.clock()

        # Если лимит <= 0, всегда отклоняем с ожиданием window_s
        if self.limit <= 0:
            return self.window_s

        # Чистим истёкшие хиты для текущего ключа
        if key in self._hits:
            self._hits[key] = deque(t for t in self._hits[key] if now - t < self.window_s)
            # Удаляем пустой ключ
            if not self._hits[key]:
                del self._hits[key]

        # Глобальная чистка примерно каждые window_s / 2 секунд или по порогу размера
        if now - self._last_global_sweep > self.window_s / 2.0 or len(self._hits) > 10000:
            self._sweep_expired_keys(now)
            self._last_global_sweep = now

        # Проверяем количество хитов в окне для текущего ключа
        hit_count = len(self._hits.get(key, deque()))

        if hit_count >= self.limit:
            # Лимит превышен, отклоняем без записи
            if key in self._hits and self._hits[key]:
                oldest_hit = self._hits[key][0]
                wait_s = self.window_s - (now - oldest_hit)
                # Возвращаем max(wait_s, small_epsilon) чтобы гарантировать > 0
                return max(wait_s, 0.001)
            else:
                # На случай race condition, возвращаем window_s
                return self.window_s

        # Разрешаем: записываем новый хит
        if key not in self._hits:
            self._hits[key] = deque()
        self._hits[key].append(now)
        return None

    def _sweep_expired_keys(self, now: float) -> None:
        """Удалить ключи, у которых истекли все хиты."""
        expired_keys = [
            key for key, hits in self._hits.items() if all(now - t >= self.window_s for t in hits)
        ]
        for key in expired_keys:
            del self._hits[key]

    def refund(self, key: str) -> None:
        """Вернуть последнюю попытку: обращение не состоялось (ресурс недоступен)."""
        hits = self._hits.get(key)
        if hits:
            hits.pop()
            if not hits:
                del self._hits[key]
