"""Эталоны знаков профиля: образцы тройных карт по каждому знаку.

Сравнение — с ближайшим образцом знака (k = 1), а не со средним: фон за строкой
сильно разный, и средняя карта размывает знак. Образцы строятся автоматически из
подписанных кадров (`stamp/build.py`) и дополняются уверенно прочитанными кадрами,
время которых подтвердила серия камеры (`stamp/eval.py --grow`).
"""

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import numpy as np


PROFILES_DIR = Path(__file__).parent / "profiles"


# Образцов на знак не больше этого: чтение кадра — доли секунды и при росте эталонов
MAX_PER_CHAR = 80
# Образец почти как уже имеющийся ничего не добавляет
NOVELTY = 0.95


class Templates:
    def __init__(self) -> None:
        self.samples: dict[str, list[np.ndarray]] = defaultdict(list)
        self._matrix: dict[str, np.ndarray] = {}  # знак → нормированные образцы строками

    def add(self, char: str, cell: np.ndarray) -> None:
        self.samples[char].append(cell.astype(np.float32))
        self._matrix.pop(char, None)

    def add_if_new(self, char: str, cell: np.ndarray) -> bool:
        """Для роста эталонов: только непохожий на имеющиеся образец и не сверх предела."""
        if len(self.samples.get(char, ())) >= MAX_PER_CHAR:
            return False
        scored = self.best(cell, char)
        if scored and scored[0][0] >= NOVELTY:
            return False
        self.add(char, cell)
        return True

    def _rows(self, char: str) -> np.ndarray:
        if char not in self._matrix:
            flat = np.stack([s.ravel() for s in self.samples[char]])
            norms = np.linalg.norm(flat, axis=1, keepdims=True)
            self._matrix[char] = flat / np.where(norms == 0, 1.0, norms)
        return self._matrix[char]

    def best(self, cell: np.ndarray, chars: Iterable[str]) -> list[tuple[float, str]]:
        """Сходство (косинус) с лучшим образцом каждого знака, по убыванию."""
        v = cell.ravel().astype(np.float32)
        n = float(np.linalg.norm(v))
        if n == 0:
            return []
        v = v / n
        scored = [
            (float((self._rows(ch) @ v).max()), ch) for ch in chars if self.samples.get(ch)
        ]
        return sorted(scored, reverse=True)

    def counts(self) -> dict[str, int]:
        return {ch: len(v) for ch, v in sorted(self.samples.items())}

    def save(self, path: Path) -> None:
        chars = [ch for ch, items in self.samples.items() for _ in items]
        maps = np.stack([m for items in self.samples.values() for m in items]).astype(np.float16)
        np.savez_compressed(path, chars=np.array(chars), maps=maps)

    @classmethod
    def load(cls, path: Path) -> "Templates":
        t = cls()
        with np.load(path) as data:
            for ch, m in zip(data["chars"], data["maps"], strict=True):
                t.add(str(ch), m.astype(np.float32))
        return t


def load_all(directory: Path = PROFILES_DIR) -> dict[str, Templates]:
    """Эталоны всех профилей: имя профиля («2592x1944») → эталоны."""
    return {p.stem: Templates.load(p) for p in sorted(directory.glob("*.npz"))}
