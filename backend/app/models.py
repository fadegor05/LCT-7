"""Единая точка импорта всех ORM-моделей — для Alembic (autogenerate).

При добавлении домена с моделями допишите сюда импорт его models, иначе Alembic
их не «увидит» и не сгенерирует миграцию.
"""

from app.core.database import Base
from app.domains.user import models as user_models  # noqa: F401

__all__ = ["Base"]
