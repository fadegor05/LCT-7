"""Сверка чисел в ответе с отчётом: метки площадок, проверка на площадку, ограничения.

Проверяет, что при выборе меток площадок учитываются только id из отчёта,
не путаются префиксы (p1 vs p10), и для многоплощадочного отчёта без названия
площадки вывод дополняется соответствующим примечанием.
"""

import sys
from pathlib import Path

import pytest

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))
sys.path.insert(0, str(ML / "tools"))

import ask_report  # noqa: E402


def by(*ids):
    """Вспомогательная функция для создания словаря by_site.

    by("p03", "p08") → {"p03": {"14", "43"}, "p08": {"77"}, "_общие": {"47"}}

    Для тестов без префиксов: первой {"14", "43"}, второй {"99"}.
    Для тестов с p-префиксами: первой {"5"}, второй {"77"}.
    """
    result = {"_общие": {"47"}}

    # Проверяем, все ли площадки с p-префиксом
    all_p_format = all(site_id.startswith('p') for site_id in ids)

    for i, site_id in enumerate(ids):
        if i == 0:
            # Первая площадка
            result[site_id] = {"5"} if all_p_format else {"14", "43"}
        elif i == 1:
            # Вторая площадка
            result[site_id] = {"77"} if all_p_format else {"99"}
        else:
            result[site_id] = {str(100 + i)}
    return result


class TestМеткиПлощадок:
    """Проверка, что site_marks находит упоминания площадок, которые есть в отчёте."""

    def test_pNN_ловит_своё_число(self):
        """Базовый случай: площадка p03 и число 14, которое ей принадлежит."""
        dict_by = by("p03")
        result = ask_report.site_marks("Площадка p03 отстаёт на 14 дней.", dict_by)
        assert len(result) == 1
        assert result[0].group(0) == "p03"

    def test_метка_не_pNN_ловит_чужое_число(self):
        """Не-pNN площадка: site-01, UUID, название на кириллице.

        Проверяет, что метки берутся из отчёта, а не из hardcoded p\\d{2}.
        Площадка A имеет {"14"}, B имеет {"99"}; в ответе число 99 приписано A,
        что должно быть поймано как ошибка.
        """
        test_cases = [
            ("site-01", "site-01 отставание 99 дней"),
            ("3f2a9c1e-7b64-4d0a-9e51-0c8d2b7a1f34", "площадка 3f2a9c1e-7b64-4d0a-9e51-0c8d2b7a1f34: 99"),
            ("Стройка-Север", "Стройка-Север: 99 дней"),
        ]
        for site_a, answer_text in test_cases:
            dict_by = by(site_a, "p99")
            result = ask_report.misattributed(answer_text, dict_by)
            assert result, f"Failed for site_id={site_a}: expected error, got {result}"
            assert f"{site_a}: 99" in result, f"Expected '{site_a}: 99', got {result}"

    def test_p1_и_p10_не_путаются(self):
        """Проверка, что p1 не ловится как префикс p10.

        "По p10" должна быть приписана p10, не p1 + "0".
        "По p1" должна быть приписана p1.
        """
        dict_by = by("p1", "p10")

        # p10 с числом 77, которое ей принадлежит — ошибок не должно
        result = ask_report.misattributed("По p10 отставание 77.", dict_by)
        assert result == [], f"Expected no errors for p10 with 77, got {result}"

        # p1 с числом 77, которое ей не принадлежит (принадлежит p10) — ошибка
        result = ask_report.misattributed("По p1 отставание 77.", dict_by)
        assert result == ["p1: 77"], f"Expected ['p1: 77'], got {result}"

    def test_pNN_поведение_прежнее(self):
        """Базовый случай работает как раньше: p03 отстаёт, но число 43 её не принадлежит."""
        # Используем ОТЧЁТ из test_pipeline.py
        report = {
            "meta": {"sites": 2, "frames_in": 47},
            "sites": [
                {"site_id": "p03", "as_of": "2023-10-13",
                 "stages": [{"stage_code": "12.3.2", "delay_days": 14,
                             "delay_days_min": 14, "delay_days_max": 43}],
                 "alerts": [], "forecast": {"shift_days": 108}},
                {"site_id": "p08", "as_of": "2024-04-24",
                 "stages": [{"stage_code": "12.3.2", "delay_days": 24,
                             "delay_days_min": 24, "delay_days_max": 55}],
                 "alerts": [], "forecast": {"shift_days": 24}},
            ],
        }
        dict_by = ask_report.numbers_by_site(ask_report.compact(report))

        # "Площадка p08 отстаёт на 43 дня" — 43 принадлежит p08, не p03
        result = ask_report.misattributed("Площадка p08 отстаёт на 43 дня.", dict_by)
        assert result == ["p08: 43"], f"Expected ['p08: 43'], got {result}"

    def test_числовые_id_не_считаются_метками(self):
        """site_id вида "1", "2" (чистые числа) не должны приниматься за метки.

        Они неотличимы от обычных чисел и должны быть исключены из меток.
        """
        dict_by = by("1", "2")
        result = ask_report.site_marks("площадка 1: 14 дней", dict_by)
        assert result == [], f"Expected no marks for purely numeric site ids, got {result}"


class TestУпоминаниеПлощадки:
    """Проверка mentions_site: находится ли хотя бы одна площадка в ответе."""

    def test_находит_упоминание_существующей_площадки(self):
        """В ответе упомянута площадка, которая есть в отчёте."""
        dict_by = by("p03")
        assert ask_report.mentions_site("Площадка p03 отстаёт на 14 дней.", dict_by) is True

    def test_не_находит_упоминания_несуществующей_площадки(self):
        """В ответе нет упоминаний площадок из отчёта."""
        dict_by = by("p03")
        assert ask_report.mentions_site("Отставание 14 дней.", dict_by) is False


class TestОграничения:
    """Проверка limits_for: нужное сообщение об ограничениях."""

    def test_limits_без_названной_площадки_при_нескольких(self):
        """Многоплощадочный отчёт, но в ответе площадка не названа.

        Должен возвращаться LIMITS + " " + NO_SITE_NOTE.
        """
        dict_by = by("p03", "p08")
        answer = "Отставание 14 дней."
        result = ask_report.limits_for(answer, dict_by)
        expected = ask_report.LIMITS + " " + ask_report.NO_SITE_NOTE
        assert result == expected, f"Expected LIMITS + NO_SITE_NOTE, got: {result}"

    def test_limits_с_названной_площадкой_без_добавки(self):
        """Многоплощадочный отчёт, но в ответе площадка названа.

        Должен возвращаться только LIMITS, без NO_SITE_NOTE.
        """
        dict_by = by("p03", "p08")
        answer = "По p03 отставание 14 дней."
        result = ask_report.limits_for(answer, dict_by)
        assert result == ask_report.LIMITS, f"Expected only LIMITS, got: {result}"
        assert ask_report.NO_SITE_NOTE not in result

    def test_limits_одна_площадка_без_добавки(self):
        """Однопаплощадочный отчёт: NO_SITE_NOTE не добавляется, даже если площадка не названа."""
        dict_by = by("p03")
        answer = "Отставание 14 дней."
        result = ask_report.limits_for(answer, dict_by)
        assert result == ask_report.LIMITS, f"Expected only LIMITS, got: {result}"
        assert ask_report.NO_SITE_NOTE not in result

    def test_limits_содержит_ограничение_про_смысл(self):
        """LIMITS должен содержать предостережение про проверку чисел, а не смысла."""
        assert "числа" in ask_report.LIMITS.lower()
        assert "смысл" in ask_report.LIMITS.lower()
