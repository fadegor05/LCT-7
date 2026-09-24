"""Единая точка импорта всех ORM-моделей — для Alembic (autogenerate).

При добавлении домена с моделями допишите сюда импорт его models, иначе Alembic
их не «увидит» и не сгенерирует миграцию.
"""

from app.core.database import Base
from app.domains.methodology import models as methodology_models  # noqa: F401
from app.domains.observation import models as observation_models  # noqa: F401
from app.domains.photo import models as photo_models  # noqa: F401
from app.domains.schedule import models as schedule_models  # noqa: F401
from app.domains.site import models as site_models  # noqa: F401
from app.domains.user import models as user_models  # noqa: F401

__all__ = ["Base"]
