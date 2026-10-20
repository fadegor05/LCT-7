"""ORM-модель камеры стройки (таблица cameras).

Камера привязана к объекту строительства. Фотографии (photos.camera_id) ссылаются на неё
необязательно. Поля захвата кадров (stream_url, capture_*) заполняются, но сам захват
появится в отдельной задаче.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Camera(Base):
    """Камера стройки; рабочая зона — полигон в долях кадра."""

    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Стрим: раз в `capture_every_s` с него снимается кадр; null — ссылки нет
    stream_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Интервал снимков; null — не снимать (ссылки нет)
    capture_every_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_capture_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Последняя попытка — по ней расписание, удачная или нет
    last_capture_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Причина последней неудачи, без учётных данных из ссылки; удача её стирает
    last_capture_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Сбоев подряд; после серии интервал растёт
    capture_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Рабочая зона: точки [x, y] в долях кадра 0–1, не меньше трёх; null — зоны нет
    zone: Mapped[list[list[float]] | None] = mapped_column(JSON, nullable=True)
    # Название рабочей зоны для текстов отклонений; null — названия нет
    zone_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
