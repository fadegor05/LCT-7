"""ORM-модель пользователя стенда (docs/DataModel.md §5.5, таблица app_user).

Авторизации в MVP нет (product.md §14, §16): в таблице живёт ровно одна строка,
она нужна, чтобы подписывать создание строек и решения по гипотезам
(«Решил: инженер [ФИО]»). Таблица названа app_user, потому что user —
зарезервированное слово в PostgreSQL.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "app_user"

    # default намеренно нет: идентификатор стендового пользователя задаётся явно
    # константой STAND_USER_ID, чтобы seed был воспроизводим между перезапусками.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
