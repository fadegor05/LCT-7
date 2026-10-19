"""Тесты для DEFAULT_RULES по двум демо-расписаниям (schedule_demo.csv и schedule_p13.csv)."""

from pathlib import Path

import pytest

from app.domains.methodology.defaults import DefaultRuleSet


class TestDefaultRulesDemoSchedules:
    """Тесты match_stage() по уникальным stage_name из обеих демо-расписаний."""

    @staticmethod
    def read_csv_stage_names(csv_path: Path) -> set[str]:
        """Прочитать уникальные stage_name из CSV файла (delimiter ';', utf-8)."""
        if not csv_path.exists():
            pytest.skip(f"CSV файл не найден: {csv_path}")

        stage_names = set()
        with open(csv_path, encoding="utf-8") as f:
            # Пропустить заголовок
            next(f)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(";")
                if len(parts) > 2:
                    stage_name = parts[2]
                    stage_names.add(stage_name)
        return stage_names

    @pytest.fixture
    def repo_root(self):
        """Корень репозитория, рассчитанный как родитель теста."""
        return Path(__file__).resolve().parents[2]

    @pytest.fixture
    def csv_stage_names(self, repo_root):
        """Собрать все уникальные stage_name из обоих демо-расписаний."""
        demo_csv = repo_root / "ml" / "data" / "reference" / "schedule_demo.csv"
        p13_csv = repo_root / "ml" / "data" / "reference" / "schedule_p13.csv"

        names = set()
        names.update(self.read_csv_stage_names(demo_csv))
        names.update(self.read_csv_stage_names(p13_csv))
        return names

    def test_all_csv_stage_names_in_test_table(self, csv_stage_names):
        """Все уникальные stage_name из CSV должны быть в таблице ниже."""
        # Таблица ожидаемых соответствий stage_name -> stage_key
        expected_table = {
            "Устройство котлована": "excavation",
            "Гидроизоляция": "waterproofing",
            "Устройство свай": "piles",
            "Устройство фундаментной плиты": "monolith",
            "Фундамент и подземная часть": "monolith",
            "Ограждение котлована: шпунт": "enclosure",
            "Земляные работы: обратная засыпка, планировка": "excavation",
            "Монолитные работы ниже отметки 0": "monolith",
            "Фасад": "facade",
            "Дорожная одежда: асфальтобетонное покрытие": "road_surface",
            "Монолитный каркас выше отметки 0": "frame",
            "Кровля": "roof",
            "Снос зданий в пятне застройки": "demolition",
            "Наружные инженерные сети": "external_networks",
        }

        table_names = set(expected_table.keys())
        missing_in_table = csv_stage_names - table_names
        assert not missing_in_table, (
            f"Следующие stage_name из CSV не в таблице ожиданий: {missing_in_table}. "
            f"Каждый новый этап требует сознательного решения."
        )

    def test_csv_stage_names_match_expected(self, csv_stage_names):
        """Каждый уникальный stage_name из CSV совпадает с ожидаемым stage_key."""
        expected_table = {
            "Устройство котлована": "excavation",
            "Гидроизоляция": "waterproofing",
            "Устройство свай": "piles",
            "Устройство фундаментной плиты": "monolith",
            "Фундамент и подземная часть": "monolith",
            "Ограждение котлована: шпунт": "enclosure",
            "Земляные работы: обратная засыпка, планировка": "excavation",
            "Монолитные работы ниже отметки 0": "monolith",
            "Фасад": "facade",
            "Дорожная одежда: асфальтобетонное покрытие": "road_surface",
            "Монолитный каркас выше отметки 0": "frame",
            "Кровля": "roof",
            "Снос зданий в пятне застройки": "demolition",
            "Наружные инженерные сети": "external_networks",
        }

        rule_set = DefaultRuleSet()
        mismatches = []

        for stage_name in sorted(csv_stage_names):
            expected_key = expected_table[stage_name]
            matched_rule = rule_set.match_stage(stage_name)
            actual_key = matched_rule.stage_key if matched_rule else None

            if actual_key != expected_key:
                mismatches.append((stage_name, expected_key, actual_key))

        assert not mismatches, "Несовпадения при match_stage():\n" + "\n".join(
            f"  '{name}': ожидается {expected}, получено {actual}"
            for name, expected, actual in mismatches
        )

    def test_negative_cases(self):
        """Отрицательные тестовые случаи (stage_name, которые НЕ должны совпадать)."""
        rule_set = DefaultRuleSet()

        # Внутренние сети не должны совпадать с наружными
        assert rule_set.match_stage("Внутренние инженерные сети") is None

        # Демонтаж перегородок не должен совпадать с демонтажом зданий
        assert rule_set.match_stage("Демонтаж перегородок") is None
