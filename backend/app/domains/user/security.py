"""Криптография для аутентификации (хеширование пароля, JWT токены)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from app.core.settings import AuthSettings
from app.plugins.exceptions import AppError

_DUMMY_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$dGVzdHNhbHQ$ZH4pIVhFSmk2WOQRqk/zOl3YZFiPfQsFf3Cni3OO7PY"
)


async def hash_password(plain: str) -> str:
    """Хешировать пароль асинхронно используя argon2-cffi.

    Выполняется в отдельном потоке, чтобы не блокировать event loop.
    """

    def _hash() -> str:
        hasher = PasswordHasher()
        return hasher.hash(plain)

    return await asyncio.to_thread(_hash)


async def verify_password(plain: str, hashed: str) -> bool:
    """Проверить пароль асинхронно.

    Выполняется в отдельном потоке, чтобы не блокировать event loop.
    Возвращает True если пароль верен, False если неверен.
    """

    def _verify() -> bool:
        try:
            hasher = PasswordHasher()
            hasher.verify(hashed, plain)
            return True
        except (VerifyMismatchError, VerificationError):
            return False

    return await asyncio.to_thread(_verify)


def create_token(user_id: uuid.UUID, settings: AuthSettings) -> str:
    """Создать JWT токен для пользователя.

    Содержит claims: sub (user_id), iat (время создания), exp (время истечения).
    Подписан с алгоритмом HS256 на secret_key.
    """
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.token_ttl_minutes)

    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }

    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return token


def decode_token(token: str, settings: AuthSettings) -> uuid.UUID:
    """Декодировать JWT токен и вернуть user_id.

    Поднимает AppError 401 если токен невалиден, истёк или подписан другим ключом.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise jwt.InvalidTokenError("No sub claim")
        return uuid.UUID(user_id_str)
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError, ValueError) as e:
        raise AppError("Требуется авторизация", status_code=401) from e


async def verify_against_dummy(plain: str) -> None:
    """Проверить пароль против фиксированного хеша для защиты от timing-атак.

    Даже если пользователь не найден, мы вызываем argon2.verify, чтобы затратить
    примерно столько же времени, сколько на проверку реального хеша.
    Ошибка не поднимается: это операция для timing equalization.
    """
    await verify_password(plain, _DUMMY_HASH)
