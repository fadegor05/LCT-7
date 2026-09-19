"""База SQLAlchemy (аналог core/Database.kt).

Здесь только декларативная база. Engine/sessionmaker/session раздаются через
DI-контейнер Dishka (см. app/plugins/di.py).
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
