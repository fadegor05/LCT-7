"""HTTP-роуты аутентификации (вход по логину и паролю)."""

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Request

from app.core.settings import Settings
from app.domains.user.auth_service import AuthService
from app.domains.user.provider import LoginRateLimiter, RegisterRateLimiter
from app.domains.user.schemas import LoginRequest, LoginResponse, RegisterRequest, UserRead
from app.plugins.exceptions import AppError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
@inject
async def login(
    body: LoginRequest,
    service: FromDishka[AuthService],
    settings: FromDishka[Settings],
    rate_limiter: FromDishka[LoginRateLimiter],
) -> LoginResponse:
    """Аутентифицировать по логину и паролю.

    Возвращает JWT токен и данные пользователя.
    Ограничена rate limiting по логину.
    """
    login_lower = body.login.strip().lower()
    wait_seconds = rate_limiter.hit(login_lower)

    if wait_seconds is not None:
        raise AppError(
            f"Слишком много попыток входа. Подождите {int(wait_seconds)} секунд",
            status_code=429,
            code="rate_limited",
        )

    token, user = await service.login(body.login, body.password)

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserRead.model_validate(user),
    )


@router.post("/register", response_model=LoginResponse, status_code=201)
@inject
async def register(
    body: RegisterRequest,
    request: Request,
    service: FromDishka[AuthService],
    rate_limiter: FromDishka[RegisterRateLimiter],
) -> LoginResponse:
    """Зарегистрироваться и сразу войти.

    Возвращает JWT токен и данные пользователя, как /auth/login. Лимит попыток — по адресу
    клиента: за Traefik это адрес прокси, так что лимит общий, он защищает от флуда.
    """
    client = request.client.host if request.client else "unknown"
    wait_seconds = rate_limiter.hit(client)

    if wait_seconds is not None:
        raise AppError(
            f"Слишком много регистраций. Подождите {int(wait_seconds)} секунд",
            status_code=429,
            code="rate_limited",
        )

    token, user = await service.register(body.login, body.password, body.full_name)

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserRead.model_validate(user),
    )
