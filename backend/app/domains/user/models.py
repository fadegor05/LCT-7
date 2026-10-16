"""ORM-модель пользователя стенда (docs/DataModel.md §5.5, таблица app_user).

Вход по логину и паролю (login, password_hash), ролей нет: пользователь владеет своими
стройками (sites.owner_id) и подписывает решения по гипотезам («Решил: инженер [ФИО]»).
Стендовый пользователь из первой версии остаётся первой строкой таблицы и получает
логин и пароль из AUTH__SEED_*. Таблица названа app_user, потому что user —
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
    login: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
