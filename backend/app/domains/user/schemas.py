"""Pydantic-схемы стендового пользователя."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    login: str | None
    created_at: datetime


class UserUpdate(BaseModel):
    # ФИО уходит в подпись «Решил: инженер [ФИО]», поэтому строка из пробелов не годится:
    # str_strip_whitespace срезает пробелы до проверки min_length.
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    """Запрос на вход: логин и пароль."""

    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RegisterRequest(BaseModel):
    """Запрос на регистрацию: логин, пароль и (необязательно) ФИО."""

    model_config = ConfigDict(str_strip_whitespace=True)

    login: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    full_name: str | None = Field(default=None, max_length=255)


class LoginResponse(BaseModel):
    """Ответ на вход: JWT токен и данные пользователя."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
