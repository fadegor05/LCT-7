"""Pydantic-схемы стендового пользователя."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    created_at: datetime


class UserUpdate(BaseModel):
    # ФИО уходит в подпись «Решил: инженер [ФИО]», поэтому строка из пробелов не годится:
    # str_strip_whitespace срезает пробелы до проверки min_length.
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=1, max_length=255)
