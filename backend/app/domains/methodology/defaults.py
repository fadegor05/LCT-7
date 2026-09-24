"""Значения по умолчанию для правил методологии проверки оборудования."""

from dataclasses import dataclass

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


@dataclass(frozen=True)
class DefaultStageRule:
    """Правило для стадии по умолчанию.

    Attributes:
        stage_key: ключ стадии (машиночитаемый идентификатор)
        title: название стадии (для отображения)
        name_keywords: кортеж ключевых слов для совпадения со сценарием (в нижнем регистре)
        sets: кортеж наборов требований (каждый набор - кортеж DefaultRequirement)
    """

    stage_key: str
    title: str
    name_keywords: tuple[str, ...]
    sets: tuple[tuple[DefaultRequirement, ...], ...]


# Правила по умолчанию для всех стадий (первое совпадение побеждает)
DEFAULT_RULES: tuple[DefaultStageRule, ...] = (
    DefaultStageRule(
        stage_key="piles",
        title="Свайные работы",
        name_keywords=("свай", "буров", "бурени"),
        sets=(
            # Набор 1: буровая установка
            (
                DefaultRequirement(
                    equipment_code="drilling_rig",
                    obligation=Obligation.NORMATIVE,
                    gesn_code="05-01-079-01",
                ),
                DefaultRequirement(
                    equipment_code="concrete_pump",
                    obligation=Obligation.NORMATIVE,
                    gesn_code="05-01-079-01",
                ),
                DefaultRequirement(
                    equipment_code="wheel_loader",
                    obligation=Obligation.NORMATIVE,
                    gesn_code="05-01-079-01",
                ),
                DefaultRequirement(
                    equipment_code="concrete_mixer",
                    min_count=1,
                    obligation=Obligation.LOGICAL,
                    source_note="по смыслу работы: бетон для свай возят миксерами",
                ),
            ),
            # Набор 2: копёр (альтернативный способ)
            (
                DefaultRequirement(
                    equipment_code="pile_driver",
                    obligation=Obligation.NORMATIVE,
                    source_note="по смыслу работы: погружение свай копром (ФСЭМ 91.02.02-001)",
                ),
                DefaultRequirement(
                    equipment_code="wheel_loader",
                    obligation=Obligation.NORMATIVE,
                    source_note="по смыслу работы",
                ),
            ),
        ),
    ),
    DefaultStageRule(
        stage_key="enclosure",
        title="Ограждение котлована (шпунт / стена в грунте)",
        name_keywords=("шпунт", "огражд", "стена в грунте", "свг"),
        sets=(
            # Набор 1: погружение шпунта
            (
                DefaultRequirement(
                    equipment_code="pile_driver",
                    obligation=Obligation.NORMATIVE,
                    source_note="по смыслу работы: погружение шпунта (ФСЭМ 91.02.02-001)",
                ),
                DefaultRequirement(
                    equipment_code="crawler_crane",
                    obligation=Obligation.AUXILIARY,
                    source_note="по смыслу работы",
                ),
            ),
            # Набор 2: стена в грунте
            (
                DefaultRequirement(
                    equipment_code="dwall_rig",
                    obligation=Obligation.NORMATIVE,
                    source_note="по смыслу работы: стена в грунте (ФСЭМ 91.02.05-031)",
                ),
                DefaultRequirement(
                    equipment_code="crawler_crane",
                    obligation=Obligation.AUXILIARY,
                    source_note="по смыслу работы",
                ),
            ),
        ),
    ),
    DefaultStageRule(
        stage_key="excavation",
        title="Разработка котлована",
        name_keywords=("котлован", "разработка грунта"),
        sets=(
            # Набор 1: экскаватор гусеничный
            (
                DefaultRequirement(
                    equipment_code="excavator_crawler",
                    obligation=Obligation.NORMATIVE,
                    source_note="по смыслу работы (ФСЭМ 91.01.05-087)",
                ),
                DefaultRequirement(
                    equipment_code="dump_truck",
                    obligation=Obligation.LOGICAL,
                    source_note="по смыслу работы: вывоз грунта",
                ),
            ),
        ),
    ),
    DefaultStageRule(
        stage_key="earthworks",
        title="Земляные работы",
        name_keywords=("земляные", "земляных", "планировк", "засыпк"),
        sets=(
            # Набор 1: бульдозер
            (
                DefaultRequirement(
                    equipment_code="bulldozer",
                    obligation=Obligation.NORMATIVE,
                    source_note="по смыслу работы (ФСЭМ 91.01.01-035)",
                ),
                DefaultRequirement(
                    equipment_code="dump_truck",
                    obligation=Obligation.LOGICAL,
                    source_note="по смыслу работы",
                ),
            ),
            # Набор 2: экскаватор колёсный
            (
                DefaultRequirement(
                    equipment_code="excavator_wheeled",
                    obligation=Obligation.NORMATIVE,
                    source_note="по смыслу работы (ФСЭМ 91.01.05-104)",
                ),
                DefaultRequirement(
                    equipment_code="dump_truck",
                    obligation=Obligation.LOGICAL,
                    source_note="по смыслу работы",
                ),
            ),
        ),
    ),
    DefaultStageRule(
        stage_key="monolith",
        title="Монолитные работы ниже нуля",
        name_keywords=("монолит", "бетонир", "фундамент"),
        sets=(
            # Набор 1: башенный кран + бетоносмеситель
            (
                DefaultRequirement(
                    equipment_code="tower_crane",
                    obligation=Obligation.NORMATIVE,
                    source_note="по смыслу работы",
                ),
                DefaultRequirement(
                    equipment_code="concrete_mixer",
                    obligation=Obligation.LOGICAL,
                    source_note="по смыслу работы",
                ),
            ),
            # Набор 2: бетононасос + бетоносмеситель
            (
                DefaultRequirement(
                    equipment_code="concrete_pump",
                    obligation=Obligation.NORMATIVE,
                    source_note="по смыслу работы (ФСЭМ 91.07.02-011)",
                ),
                DefaultRequirement(
                    equipment_code="concrete_mixer",
                    obligation=Obligation.LOGICAL,
                    source_note="по смыслу работы",
                ),
            ),
        ),
    ),
    DefaultStageRule(
        stage_key="frame",
        title="Возведение каркаса",
        name_keywords=("каркас",),
        sets=(
            # Набор 1: башенный кран
            (
                DefaultRequirement(
                    equipment_code="tower_crane",
                    obligation=Obligation.NORMATIVE,
                    source_note="по смыслу работы",
                ),
            ),
            # Набор 2: автокран
            (
                DefaultRequirement(
                    equipment_code="truck_crane",
                    obligation=Obligation.NORMATIVE,
                    source_note="по смыслу работы (ФСЭМ 91.05.05-015)",
                ),
            ),
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
        """Найти правило по названию стадии (case-insensitive substring match).

        Возвращает первое совпадение из DEFAULT_RULES.
        Ключевые слова проверяются как подстроки в нижнем регистре названия.

        Args:
            stage_name: название стадии из графика

        Returns:
            DefaultStageRule или None если не найдено совпадение
        """
        stage_name_lower = stage_name.lower()
        for rule in self.rules:
            for keyword in rule.name_keywords:
                if keyword in stage_name_lower:
                    return rule
        return None
