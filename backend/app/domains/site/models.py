"""ORM-модель объекта строительства (docs/DataModel.md §5.2, таблица sites)."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Тип объекта (clean-mvp): жильё, образование, здравоохранение, другое
    object_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="other", server_default="other"
    )
    # Рабочие дни, date.weekday(): пн=0…вс=6. В нерабочий день отсутствие техники — не
    # отклонение (вход движка)
    workdays: Mapped[list[int]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: [0, 1, 2, 3, 4],
        server_default=text("'[0, 1, 2, 3, 4]'"),
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app_user.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
