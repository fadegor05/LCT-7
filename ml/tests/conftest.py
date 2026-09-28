"""Конфигурация pytest для ml/tests.

Обеспечивает импорт модулей service/ из ml/ при запуске из ml/.
"""

import sys
from pathlib import Path

import pytest

# Добавляем ml/ в sys.path, чтобы импорты работали
ml_dir = Path(__file__).resolve().parent.parent
if str(ml_dir) not in sys.path:
    sys.path.insert(0, str(ml_dir))


@pytest.fixture
def llm_env(monkeypatch, tmp_path):
    """Фиксирует переменные LLM_* и точит suggest_stage_mapping.ML на tmp_path.

    Возвращает функцию set(base_url=..., api_key=..., model=...) для установки значений.
    """
    # Удаляем переменные окружения
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    # Перенаправляем suggest_stage_mapping.ML
    import suggest_stage_mapping
    monkeypatch.setattr(suggest_stage_mapping, "ML", tmp_path)

    def set(base_url=None, api_key=None, model=None):
        """Устанавливает переменные окружения."""
        if base_url is not None:
            monkeypatch.setenv("LLM_BASE_URL", base_url)
        if api_key is not None:
            monkeypatch.setenv("LLM_API_KEY", api_key)
        if model is not None:
            monkeypatch.setenv("LLM_MODEL", model)

    return set
