"""Работы графика → крупные этапы (перенесено из clean-mvp)."""

from datetime import date

from app.domains.schedule.grouping import group_works
from app.domains.schedule.parser import ParsedRow


def row(number, name, start=None, end=None, n=0):
    s = date.fromisoformat(start) if start else None
    e = date.fromisoformat(end) if end else None
    return ParsedRow(name=name, start=s, end=e, number=number)


def test_demo_schedule_groups_by_first_number() -> None:
    rows = [
        row("1.1", "Устройство сети временной ливневой канализации", "2026-07-20", "2026-08-02"),
        row("2.1", "Земляные работы. Устройство основания под здание", "2026-07-20", "2026-09-05"),
        row("3.1", "Работы по устройству фундамента под башенный кран", "2026-07-20", "2026-08-02"),
        row("4.1", "Устройство монолитного каркаса здания", "2026-08-03", "2026-09-14"),
        row("4.2", "Устройство каркаса здания из металлоконструкций", "2026-08-03", "2026-09-14"),
        row("6", "Работы по устройству кровли", "2026-08-25", "2026-09-05"),
    ]
    stages = group_works(rows)
    assert [s.name for s in stages] == [
        "Устройство сети временной ливневой канализации",
        "Земляные работы. Устройство основания под здание",
        "Работы по устройству фундамента под башенный кран",
        "Устройство монолитного каркаса здания",
        "Работы по устройству кровли",
    ]
    frame = stages[3]
    assert [w.number for w in frame.works] == ["4.1", "4.2"]
    assert (frame.start, frame.end, frame.windows) == (date(2026, 8, 3), date(2026, 9, 14), 2)


def test_parent_row_without_dates_names_the_stage() -> None:
    stages = group_works(
        [
            row("2", "Земляные работы."),
            row("2.1", "Устройство основания", "2026-05-15", "2026-11-30"),
        ]
    )
    assert len(stages) == 1
    assert stages[0].name == "Земляные работы"
    assert [w.number for w in stages[0].works] == ["2.1"]


def test_parent_row_with_dates_is_also_a_work() -> None:
    stages = group_works(
        [
            row("1", "Подготовительный период", "2026-04-10", "2026-05-22"),
            row("1.1", "Ливневая канализация", "2026-05-15", "2026-08-30"),
        ]
    )
    assert [w.number for w in stages[0].works] == ["1", "1.1"]
    assert (stages[0].start, stages[0].end) == (date(2026, 4, 10), date(2026, 8, 30))


def test_lone_parent_without_dates_stays_a_stage_without_dates() -> None:
    stages = group_works(
        [row("11", "Благоустройство"), row("12", "Отделка", "2027-06-01", "2027-12-15")]
    )
    assert [s.name for s in stages] == ["Благоустройство", "Отделка"]
    assert stages[0].start is None and [w.number for w in stages[0].works] == ["11"]


def test_rows_without_number_become_own_stages_in_file_order() -> None:
    stages = group_works([row(None, "Котлован", "2026-01-01", "2026-01-10"), row(None, "Кровля")])
    assert [s.name for s in stages] == ["Котлован", "Кровля"]


def test_stage_window_ignores_works_without_dates() -> None:
    stages = group_works([row("3.1", "Плита", "2026-07-15", "2026-11-30"), row("3.2", "Насосные")])
    assert (stages[0].start, stages[0].end, stages[0].windows) == (
        date(2026, 7, 15),
        date(2026, 11, 30),
        1,
    )


def test_stage_name_drops_the_list_after_a_colon() -> None:
    long = (
        "Работы подготовительного периода: - вынос в натуру линий регулирования застройки "
        "и создание геодезической разбивочной основы; - установка временного ограждения"
    )
    stages = group_works([row("1", long, "2026-04-10", "2026-05-22")])
    assert stages[0].name == "Работы подготовительного периода"
    # Работа — с полным текстом
    assert stages[0].works[0].name == long


def test_stage_name_keeps_a_short_qualifier_after_a_colon() -> None:
    stages = group_works([row("2", "Ограждение котлована: шпунт", "2026-07-01", "2026-08-31")])
    assert stages[0].name == "Ограждение котлована: шпунт"
