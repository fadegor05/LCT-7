"""Значения по умолчанию для правил методологии проверки оборудования.

Семейства этапов и их техника — как в clean-mvp (`catalog/kits.py`, из методики ML
`ml/configs/rules.json`, решения D-011 и D-015). Семейство определяется по словам в
названии этапа; порядок важен: частные формулировки стоят выше общих.

В clean-mvp у этапа один комплект, и любая его нормативная машина — маркер. Здесь
этап подтверждает набор, если на месте вся его нормативная техника (#54), поэтому
каждая нормативная машина семейства — свой набор вместе с логической и вспомогательной
техникой: наборы — альтернативы, и этап подтверждает любая из его машин, как в clean.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.domains.methodology.models import Obligation


@dataclass(frozen=True)
class DefaultRequirement:
    """Требование по умолчанию для оборудования.

    Attributes:
        equipment_code: код типа оборудования (из EQUIPMENT_SEED)
        min_count: минимальное количество единиц (по умолчанию 1)
        obligation: обязательность (normative, logical, auxiliary)
        gesn_code: код ГЭСН (если есть)
        source_note: источник/примечание (если нет ГЭСН)
    """

    equipment_code: str
    min_count: int = 1
    obligation: Obligation = Obligation.NORMATIVE
    gesn_code: str | None = None
    source_note: str | None = None
    # Группа взаимозаменяемой техники: этапу хватает любой её машины
    group_code: str | None = None


@dataclass(frozen=True)
class DefaultStageRule:
    """Правило для стадии по умолчанию.

    Attributes:
        stage_key: ключ стадии (машиночитаемый идентификатор)
        title: название стадии (для отображения)
        name_keywords: подстроки названия в нижнем регистре (если нет `pattern`)
        sets: кортеж наборов требований (каждый набор - кортеж DefaultRequirement)
        pattern: регулярное выражение по названию этапа (без учёта регистра)
        unchecked_reason: этап по технике не проверяется — почему (наборов тогда нет)
    """

    stage_key: str
    title: str
    name_keywords: tuple[str, ...]
    sets: tuple[tuple[DefaultRequirement, ...], ...]
    pattern: str = ""
    unchecked_reason: str | None = None

    def matches(self, stage_name: str) -> bool:
        if self.pattern:
            return re.search(self.pattern, stage_name, re.IGNORECASE) is not None
        lower = stage_name.lower()
        return any(keyword in lower for keyword in self.name_keywords)


# Группа «Сваебойная и буровая техника» — любая из этих машин подтверждает сваи
PILING = ("drilling_rig", "pile_driver", "dwall_rig")


def _n(code: str, source: str, rule: str) -> tuple[str, DefaultRequirement]:
    gesn = source.removeprefix("ГЭСН ").strip() if source.startswith("ГЭСН") else None
    return "n", DefaultRequirement(
        code, obligation=Obligation.NORMATIVE, gesn_code=gesn, source_note=rule
    )


def _l(code: str, rule: str) -> tuple[str, DefaultRequirement]:
    return "o", DefaultRequirement(
        code, obligation=Obligation.LOGICAL, source_note=f"по смыслу работы: {rule}"
    )


def _a(code: str, rule: str) -> tuple[str, DefaultRequirement]:
    return "o", DefaultRequirement(
        code, obligation=Obligation.AUXILIARY, source_note=f"по смыслу работы: {rule}"
    )


def _family(
    key: str,
    title: str,
    pattern: str,
    *reqs: tuple[str, DefaultRequirement],
    reason: str | None = None,
) -> DefaultStageRule:
    """Набор на каждую нормативную машину семейства, к ней — вся сопутствующая техника."""
    normative = [r for kind, r in reqs if kind == "n"]
    others = tuple(r for kind, r in reqs if kind == "o")
    sets = tuple((n, *others) for n in normative)
    return DefaultStageRule(
        stage_key=key,
        title=title,
        name_keywords=(),
        sets=sets,
        pattern=pattern,
        unchecked_reason=reason,
    )


# Правила по умолчанию для всех стадий (первое совпадение побеждает)
DEFAULT_RULES: tuple[DefaultStageRule, ...] = (
    _family(
        "preparation",
        "Подготовка территории",
        r"подготовительн|подготовка территори",
        _n("bulldozer", "ГЭСН 01-01-036-01", "Расчистка и планировка территории бульдозером"),
        _n("excavator_crawler", "ГЭСН 46-06-009-01", "Демонтаж и корчёвка экскаватором"),
        _l("dump_truck", "Вывоз мусора и грунта самосвалами"),
        _a("truck_crane", "Монтаж временных сооружений автокраном"),
    ),
    _family(
        "demolition",
        "Снос зданий",
        r"снос|демонтаж сущ|демонтаж зданий|демонтаж строени|вырубк",
        _n("excavator_crawler", "ГЭСН 46-06-009-01", "Обрушение конструкций экскаватором"),
        _l("dump_truck", "Вывоз строительного мусора самосвалами"),
        _a("bulldozer", "Планировка после сноса бульдозером"),
        _a("truck_crane", "Подъём демонтируемых элементов автокраном"),
    ),
    _family(
        "enclosure",
        "Ограждение котлована: шпунт",
        r"шпунт|ограждени[ея] котлован|ограждающих конструкций котлован",
        _n("pile_driver", "ГЭСН 05-01-089-01", "Погружение шпунта вибропогружателем"),
        _n("crawler_crane", "ГЭСН 05-01-011-01", "Подача шпунта гусеничным краном"),
        _a("truck_crane", "Разгрузка шпунта автокраном"),
    ),
    _family(
        "diaphragm_wall",
        "Стена в грунте",
        r"стена в грунте|свг",
        _n("dwall_rig", "ГЭСН 05-03-010-01", "Разработка траншеи грейфером"),
        _n("crawler_crane", "ГЭСН 05-03-010-01", "Установка каркасов гусеничным краном"),
        _n("concrete_mixer", "ГЭСН 05-03-010-01", "Подача бетона автобетоносмесителем"),
        _l("dump_truck", "Вывоз грунта самосвалами"),
    ),
    _family(
        "piles",
        "Устройство свай",
        r"сва[ий]|свайн|буронабивн|буров|бурени",
        *(
            ("n", replace(req, group_code="piling"))
            for _, req in (
                _n(code, "ГЭСН 05-01-028-01, 05-01-001-01", "Бурение или погружение свай")
                for code in PILING
            )
        ),
        _a("crawler_crane", "Установка арматурных каркасов гусеничным краном"),
        _l("concrete_mixer", "Подача бетона в скважину"),
    ),
    _family(
        "external_networks",
        "Наружные инженерные сети",
        r"наружн\w* (?:\w+ )?(?:сет|инженерн|водоснаб|водоотвед|электроснаб|освещ|газо)|"
        r"тепловая сеть|газопровод|ливнев|канализац",
        _n("excavator_crawler", "ГЭСН 01-01-022-05", "Разработка траншеи экскаватором"),
        _n("truck_crane", "ГЭСН 22-01-021-01", "Укладка труб автокраном"),
        _n("backhoe_loader", "ГЭСН 01-01-022-05", "Разработка траншеи экскаватором-погрузчиком"),
        _l("dump_truck", "Вывоз грунта самосвалами"),
    ),
    _family(
        "excavation",
        "Котлован и земляные работы",
        r"котлован|разработка грунта|выемка грунта|земляные работ|земляных работ",
        _n("excavator_crawler", "ГЭСН 01-01-013-05", "Разработка грунта экскаватором"),
        _n("bulldozer", "ГЭСН 01-01-013-05", "Перемещение грунта бульдозером"),
        _l("dump_truck", "Вывоз грунта самосвалами"),
        _a("wheel_loader", "Погрузка грунта фронтальным погрузчиком"),
    ),
    _family(
        "earthworks",
        "Обратная засыпка, планировка, основание",
        r"обратн\w+ засыпк|засыпк|планировк|уплотнени|устройство основани",
        _n("bulldozer", "ГЭСН 01-01-033-01", "Засыпка и планировка бульдозером"),
        _n("roller", "ГЭСН 01-02-001-01", "Уплотнение грунта катком"),
        _n("grader", "ГЭСН 01-01-036-01", "Планировка автогрейдером"),
        _l("dump_truck", "Подвоз грунта самосвалами"),
    ),
    _family(
        "monolith",
        "Фундамент и подземная часть",
        r"фундамент|монолитн\w+ работ.*ниже|подземн\w+ част|бетонир",
        _n("concrete_pump", "ГЭСН 06-01-003-08", "Бетонирование автобетононасосом"),
        _l("concrete_mixer", "Подвоз бетона автобетоносмесителем"),
        _a("truck_crane", "Монтаж арматуры и опалубки автокраном"),
    ),
    _family(
        "road_surface",
        "Дорожная одежда",
        r"асфальт|проезд|тротуар|дорожн\w+ одежд",
        _n("paver", "ГЭСН 27-06-029-01", "Укладка асфальтобетона асфальтоукладчиком"),
        _n("roller", "ГЭСН 27-06-029-01", "Уплотнение асфальтобетона катком"),
        _l("dump_truck", "Подвоз смеси самосвалами"),
    ),
    _family(
        "frame",
        "Каркас здания",
        r"каркас|несущих конструкц|перекрыти|металлоконструкц",
        _n("tower_crane", "ГЭСН 06-05-002-01", "Подача материалов башенным краном"),
        _l("concrete_mixer", "Подвоз бетона автобетоносмесителем"),
        _a("concrete_pump", "Бетонирование автобетононасосом"),
        _a("truck_crane", "Монтаж конструкций автокраном"),
    ),
    _family(
        "roof",
        "Кровля",
        r"кровл",
        reason=(
            "башенный кран стоит на площадке независимо от этапа, кровельной техники в классах нет"
        ),
    ),
    _family(
        "facade",
        "Фасад",
        r"фасад|ограждающих конструкц",
        reason="фасадных подъёмников и люлек нет в классах детектора",
    ),
    _family(
        "waterproofing",
        "Гидроизоляция",
        r"гидроизоляц",
        reason=(
            "из машин в норме только бортовой автомобиль, работа видна по сцене, а не по технике"
        ),
    ),
)


class DefaultRuleSet:
    """Набор правил по умолчанию (stateless, APP-scoped)."""

    @property
    def rules(self) -> tuple[DefaultStageRule, ...]:
        """Получить все правила по умолчанию."""
        return DEFAULT_RULES

    def match_stage(self, stage_name: str) -> DefaultStageRule | None:
        """Найти правило по названию стадии: первое совпавшее семейство из DEFAULT_RULES.

        Args:
            stage_name: название стадии из графика

        Returns:
            DefaultStageRule или None если не найдено совпадение
        """
        return next((rule for rule in self.rules if rule.matches(stage_name)), None)

    def match_stage_or_works(
        self, stage_name: str, work_names: Sequence[str] | None
    ) -> DefaultStageRule | None:
        """Семейство по названию этапа, а если оно общее — по названиям его работ (clean-mvp:
        «Работы по устройству котельной» с работой «Устройство фундамента» — фундамент)."""
        for name in (stage_name, *(work_names or ())):
            found = self.match_stage(name)
            if found is not None:
                return found
        return None
