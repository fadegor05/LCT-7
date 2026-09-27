"""Конфигурация pytest для ml/tests.

Обеспечивает импорт модулей service/ из ml/ при запуске из ml/.
"""

import sys
from pathlib import Path

# Добавляем ml/ в sys.path, чтобы импорты работали
ml_dir = Path(__file__).resolve().parent.parent
if str(ml_dir) not in sys.path:
    sys.path.insert(0, str(ml_dir))
