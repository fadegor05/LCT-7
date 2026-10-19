"""Работы графика → крупные этапы (как в clean-mvp, schedule/grouping.py).

Работы с номером объединяются по первому уровню нумерации: «2.1», «2.2» → этап «2».
Название этапа — строка-родитель («2 Земляные работы»), а если её нет — первая работа
группы; окно этапа — от самого раннего начала до самого позднего окончания его работ.
Родитель с датами сам считается работой. Работы без номера — каждая своим этапом.

Без этого 59 строк графика Березников давали 45 этапов, а название первого — абзац
перечня работ («Работы подготовительного периода: - вынос в натуру…; - установка…»).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from app.domains.schedule.parser import ParsedRow

# После двоеточия — перечень работ, а не уточнение: «Работы подготовительного периода: -
# вынос в натуру…; - установка ограждения; …». Короткое «Ограждение котлована: шпунт» — нет
LIST_AFTER_COLON_CHARS = 60


@dataclass
class GroupedStage:
    name: str
    works: list[ParsedRow] = field(default_factory=list)

    @property
    def start(self) -> date | None:
        starts = [w.start for w in self.works if w.start is not None]
        return min(starts) if starts else None

    @property
    def end(self) -> date | None:
        ends = [w.end for w in self.works if w.end is not None]
        return max(ends) if ends else None

    @property
    def windows(self) -> int:
        """Сколько окон работ слито в окно этапа."""
        return sum(1 for w in self.works if w.start is not None and w.end is not None)


def stage_title(name: str) -> str:
    """Название этапа: без точки на конце и без перечня работ после двоеточия."""
    title = name.strip().rstrip(".").strip()
    head, colon, tail = title.partition(":")
    tail = tail.strip()
    if (
        colon
        and head.strip()
        and (tail.startswith(("-", "–", "—", "•")) or len(tail) > LIST_AFTER_COLON_CHARS)
    ):
        return head.strip()
    return title


def group_works(rows: Sequence[ParsedRow]) -> list[GroupedStage]:
    """Работы в порядке графика → этапы в порядке первого появления группы."""
    groups: dict[str, GroupedStage] = {}
    headers: dict[str, ParsedRow] = {}
    for i, row in enumerate(rows):
        if row.number is not None:
            key = row.number.split(".")[0]
            is_parent = "." not in row.number
        else:
            key, is_parent = f"row:{i}", False
        group = groups.get(key)
        if group is None:
            group = groups[key] = GroupedStage(name=stage_title(row.name))
        if is_parent:
            group.name = stage_title(row.name)
            if row.start is None and row.end is None:
                headers[key] = row  # родитель без дат — заголовок группы, не работа
                continue
        group.works.append(row)
    for key, header in headers.items():
        if not groups[key].works:
            groups[key].works.append(header)
    return list(groups.values())
