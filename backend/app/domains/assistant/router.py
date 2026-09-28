"""HTTP-роуты для ассистента."""

import uuid

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from app.domains.assistant.ask_service import AssistantService
from app.domains.assistant.schemas import AskRequest, AssistantAnswerRead, AssistantStatusRead

router = APIRouter(tags=["assistant"])


@router.post("/sites/{site_id}/assistant/ask")
@inject
async def ask(
    site_id: uuid.UUID,
    request: AskRequest,
    service: FromDishka[AssistantService],
) -> AssistantAnswerRead:
    """Задать вопрос по отчёту.

    Args:
        site_id: ID площадки
        request: Запрос с вопросом
        service: Сервис ассистента

    Returns:
        AssistantAnswerRead с ответом, ссылками на этапы и метаинформацией

    Raises:
        404: Площадка не найдена, не принадлежит пользователю или график не загружен
        422: Вопрос короче 3 или длиннее 500 символов (валидация)
             или выходит за рамки отчёта (scope guard)
        429: Превышен лимит частоты запросов
        413: Отчёт слишком большой для отправки ассистенту
        503: Ассистент недоступен
        504: Ассистент не ответил вовремя
        400: Ассистент вернул ошибку
    """
    return await service.ask(site_id, request.question)


@router.get("/assistant/status")
@inject
async def status(service: FromDishka[AssistantService]) -> AssistantStatusRead:
    """Получить статус доступности ассистента.

    Args:
        service: Сервис ассистента

    Returns:
        AssistantStatusRead с флагом доступности

    Raises:
        Не выбрасывает исключения; статус никогда не потребляет квоту к ML.
    """
    return await service.status()
