# Система уведомлений — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** У пользователя появляется личная лента уведомлений — в БД, в шторке на сайте и, по его выбору, в телеграме.

**Architecture:** Новый домен `notification` в бэкенде хранит уведомления и привязки каналов. Доставка идёт через адаптеры канала (`NotificationChannel` Protocol) за реестром в `Scope.APP`; реально реализован только телеграм. Привязка телеграма — одноразовый токен в БД плюс фоновый long-polling бота, устроенный как существующий `StreamCapture`. На фронте — новый примитив `Drawer`, шторка с лентой и страница профиля с управлением каналами.

**Tech Stack:** FastAPI, Dishka, SQLAlchemy 2 (async), Alembic, Pydantic v2, httpx, pytest; React 19, TanStack Query, Zod, CSS Modules, MSW, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-18-notifications-design.md`

## Global Constraints

- Тип уведомления и вид канала — питоновский `StrEnum` плюс колонка `String(n)`. Постгресовых `ENUM` не создавать ни при каких условиях.
- Каждая новая ORM-модель импортируется в `backend/app/models.py`, иначе Alembic её не увидит.
- Коммит — ответственность сервиса. Репозиторий только `flush()` (см. `backend/app/core/repository.py`).
- Доменные ошибки — `AppError(message, status_code)` из `app/plugins/exceptions.py`, сообщения по-русски и для пользователя.
- Токен бота никогда не попадает в логи. `chat_id` в ответах API маскируется.
- Каждый новый фронтовый компонент получает свой `*.test.tsx`.
- Ответы API на фронте проходят через `request()` с zod-схемой — других путей к сети нет.
- Пороги покрытия фронта: `statements 90`, `branches 85`, `functions 90`, `lines 90` (`frontend/vite.config.ts:54`).
- `make check` и `make front-check` должны проходить на каждом коммите.
- Комментарии и докстринги — по-русски, как во всём бэкенде.

## Review Focus

1. **`POST /notifications/read` не должен трогать чужие уведомления.** Два пользователя, у каждого непрочитанные; один помечает прочитанным — у второго ничего не меняется. Тест в Task 3.
2. **Повторное погашение токена привязки.** Второй `/start` с тем же токеном не создаёт вторую привязку и отвечает «ссылка устарела». Тест в Task 9.
3. **Телеграм отвечает ошибкой (403, бот заблокирован пользователем).** Создание уведомления остаётся успешным, ошибка уходит в лог, привязка не удаляется. Тест в Task 7.
4. **Текст длиннее лимита Telegram (4096 символов).** Сообщение обрезается, а не роняет отправку. Тест в Task 6.
5. **Пустая лента.** `unread_count = 0`, бейдж скрыт, открытие шторки не шлёт `POST /notifications/read`. Тест в Task 13.

---

## Структура файлов

**Бэкенд, создаётся:**

| Файл | Ответственность |
|---|---|
| `backend/app/domains/notification/models.py` | `NotificationType`, `ChannelKind`, ORM-модели трёх таблиц |
| `backend/app/domains/notification/schemas.py` | Pydantic-схемы запросов и ответов |
| `backend/app/domains/notification/repository.py` | три репозитория поверх `BaseRepository` |
| `backend/app/domains/notification/service.py` | `NotificationService` — лента, пометка прочитанным, `notify()` |
| `backend/app/domains/notification/channels.py` | `ChannelLinkService` — выдача и погашение токенов, привязки |
| `backend/app/domains/notification/dispatcher.py` | `NotificationDispatcher` Protocol, `NullDispatcher`, `BackgroundDispatcher` |
| `backend/app/domains/notification/telegram_link.py` | `TelegramLinkPoller` и `start_telegram_poller` |
| `backend/app/domains/notification/router.py` | роуты `/notifications` и `/users/me/channels` |
| `backend/app/domains/notification/provider.py` | DI-провайдеры домена |
| `backend/app/adapters/notify/base.py` | `ChannelMessage`, `NotifyError`, `NotificationChannel` Protocol |
| `backend/app/adapters/notify/log.py` | `LogChannel` — умолчание и то, что видят тесты |
| `backend/app/adapters/notify/telegram.py` | `TelegramClient`, `TelegramChannel` |
| `backend/app/adapters/notify/factory.py` | `ChannelRegistry` и её сборка по настройкам |
| `backend/alembic/versions/0013_*.py` | миграция трёх таблиц |

**Бэкенд, правится:** `app/core/settings.py` (секция `notify`), `app/models.py`, `app/plugins/di.py`, `app/plugins/routing.py`, `app/main.py` (lifespan), `backend/tests/conftest.py` (тестовые провайдеры), `.env.dist`.

**Фронт, создаётся:**

| Файл | Ответственность |
|---|---|
| `frontend/src/components/ui/useDismissable.ts` | Escape и возврат фокуса; общий для `Dialog` и `Drawer` |
| `frontend/src/components/ui/Drawer.tsx` + `.module.css` | панель справа на всю высоту |
| `frontend/src/api/notifications.ts` | функции API и хуки TanStack Query |
| `frontend/src/features/notifications/NotificationBell.tsx` | иконка с бейджем, владеет состоянием шторки |
| `frontend/src/features/notifications/NotificationDrawer.tsx` | лента, снимок непрочитанных, пустое состояние |
| `frontend/src/features/notifications/NotificationItem.tsx` | одно уведомление |
| `frontend/src/features/profile/ChannelList.tsx` | карточки каналов: привязать, отвязать, тумблер |
| `frontend/src/pages/ProfilePage.tsx` | личный кабинет |

**Фронт, правится:** `components/ui/Dialog.tsx` (переход на хук), `components/ui/Icon.tsx` (иконка `bell`), `components/layout/AppLayout.tsx`, `api/schemas.ts`, `api/keys.ts`, `app/routes.tsx`, `mocks/db.ts`, `mocks/handlers.ts`, `mocks/fixtures.ts`.

---

## Task 1: Настройки канала уведомлений

**Files:**
- Modify: `backend/app/core/settings.py` (добавить класс рядом с `AuthSettings`, поле в `Settings`)
- Modify: `.env.dist`
- Test: `backend/tests/test_notify_settings.py`

**Interfaces:**
- Consumes: ничего
- Produces: `TelegramSettings`, `NotifySettings`; `Settings.notify: NotifySettings`; свойства `NotifySettings.telegram_configured: bool`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_notify_settings.py`:

```python
"""Настройки уведомлений: без токена канал считается ненастроенным."""

from app.core.settings import NotifySettings, Settings


def test_telegram_not_configured_by_default() -> None:
    settings = NotifySettings()

    assert settings.telegram.token is None
    assert settings.telegram_configured is False


def test_telegram_configured_requires_both_token_and_username() -> None:
    """Ссылку t.me собрать не из чего, если нет имени бота — считаем ненастроенным."""
    only_token = NotifySettings.model_validate({"telegram": {"token": "123:abc"}})
    both = NotifySettings.model_validate(
        {"telegram": {"token": "123:abc", "bot_username": "lct7_bot"}}
    )

    assert only_token.telegram_configured is False
    assert both.telegram_configured is True


def test_settings_exposes_notify_section() -> None:
    assert isinstance(Settings().notify, NotifySettings)


def test_public_url_strips_trailing_slash() -> None:
    """Ссылки склеиваются конкатенацией — двойной слеш в URL недопустим."""
    settings = NotifySettings.model_validate({"public_url": "https://example.com/"})

    assert settings.public_url == "https://example.com"
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd backend && uv run pytest tests/test_notify_settings.py -v`
Expected: FAIL — `ImportError: cannot import name 'NotifySettings'`

- [ ] **Step 3: Реализовать настройки**

В `backend/app/core/settings.py` добавить после `AuthSettings`:

```python
class TelegramSettings(BaseModel):
    """Параметры телеграм-бота. Без токена канал деградирует в запись в лог."""

    token: str | None = None
    # Имя бота без @ — из него собирается ссылка привязки t.me/<bot>?start=<token>
    bot_username: str | None = None
    # Таймаут long polling; телеграм держит соединение до появления апдейта
    poll_timeout_s: int = 25
    request_timeout_s: float = 35.0


class NotifySettings(BaseModel):
    """Доставка уведомлений по каналам."""

    telegram: TelegramSettings = TelegramSettings()
    # База для абсолютных ссылок в сообщениях: в письме относительный путь бесполезен
    public_url: str = "http://localhost"

    @field_validator("public_url")
    @classmethod
    def _strip_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram.token and self.telegram.bot_username)
```

В классе `Settings` рядом с `auth: AuthSettings = AuthSettings()` добавить:

```python
    notify: NotifySettings = NotifySettings()
```

- [ ] **Step 4: Запустить тест и убедиться, что проходит**

Run: `cd backend && uv run pytest tests/test_notify_settings.py -v`
Expected: PASS, 4 passed

- [ ] **Step 5: Дописать `.env.dist`**

Добавить в конец `.env.dist`:

```
# Уведомления: телеграм-бот для доставки.
# Пусто или отсутствует -> сообщения только пишутся в лог приложения,
# кнопка привязки в личном кабинете отвечает «канал не настроен».
# Токен берётся у @BotFather, имя бота — без символа @.
# NOTIFY__TELEGRAM__TOKEN=
# NOTIFY__TELEGRAM__BOT_USERNAME=

# База для абсолютных ссылок в сообщениях (без завершающего слеша)
NOTIFY__PUBLIC_URL=http://localhost
```

- [ ] **Step 6: Прогнать линтер и закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make pretty && make check
git add backend/app/core/settings.py backend/tests/test_notify_settings.py .env.dist
git commit -m "feat(backend): настройки канала уведомлений"
```

---

## Task 2: Модели и миграция

**Files:**
- Create: `backend/app/domains/notification/__init__.py` (пустой)
- Create: `backend/app/domains/notification/models.py`
- Modify: `backend/app/models.py`
- Create: `backend/alembic/versions/0013_notifications.py` (имя файла даст автогенерация)
- Test: `backend/tests/test_notification_model.py`

**Interfaces:**
- Consumes: `app.core.database.Base`
- Produces: `NotificationType`, `ChannelKind`, `Notification`, `UserChannel`, `ChannelLinkToken`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_notification_model.py`:

```python
"""Схема уведомлений: типы — строки, а не постгресовый ENUM."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from dishka import AsyncContainer
from sqlalchemy import String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notification.models import (
    ChannelKind,
    ChannelLinkToken,
    Notification,
    NotificationType,
    UserChannel,
)
from app.domains.user.service import STAND_USER_ID, UserService


async def seed_user(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


def test_type_column_is_a_string_not_a_db_enum() -> None:
    """Расширение списка типов не должно требовать миграции."""
    assert isinstance(Notification.__table__.c.type.type, String)
    assert isinstance(UserChannel.__table__.c.channel.type, String)


def test_enums_are_str_enums() -> None:
    assert NotificationType.SYSTEM == "system"
    assert ChannelKind.TELEGRAM == "telegram"


async def test_notification_round_trip(container: AsyncContainer) -> None:
    await seed_user(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(
            Notification(
                user_id=STAND_USER_ID,
                type=NotificationType.SYSTEM,
                title="Проверка",
                body="Тело уведомления",
                link="/sites",
            )
        )
        await session.commit()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        stored = (await session.execute(select(Notification))).scalar_one()

        assert stored.title == "Проверка"
        assert stored.read_at is None
        assert stored.created_at is not None


async def test_one_channel_binding_per_user(container: AsyncContainer) -> None:
    """Второй телеграм у того же пользователя — нарушение уникальности."""
    await seed_user(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add_all(
            [
                UserChannel(
                    user_id=STAND_USER_ID, channel=ChannelKind.TELEGRAM, address="111"
                ),
                UserChannel(
                    user_id=STAND_USER_ID, channel=ChannelKind.TELEGRAM, address="222"
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_link_token_round_trip(container: AsyncContainer) -> None:
    await seed_user(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(
            ChannelLinkToken(
                token="a" * 32,
                user_id=STAND_USER_ID,
                channel=ChannelKind.TELEGRAM,
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            )
        )
        await session.commit()

        stored = (await session.execute(select(ChannelLinkToken))).scalar_one()
        assert stored.used_at is None
        assert len(stored.token) == 32
        assert stored.user_id == STAND_USER_ID
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd backend && uv run pytest tests/test_notification_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domains.notification'`

- [ ] **Step 3: Создать модели**

Создать пустой `backend/app/domains/notification/__init__.py` и `backend/app/domains/notification/models.py`:

```python
"""ORM-модели уведомлений, привязок каналов и токенов привязки.

Тип уведомления и вид канала — питоновские StrEnum поверх колонки String, а не
постгресовый ENUM: список типов пополняется доменами-источниками, и новый тип не
должен требовать миграции.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NotificationType(StrEnum):
    """Тип уведомления. Домены-источники добавляют свои значения сюда."""

    SYSTEM = "system"


class ChannelKind(StrEnum):
    """Канал доставки. Почта и СМС появятся отдельными адаптерами."""

    TELEGRAM = "telegram"


class Notification(Base):
    """Уведомление для одного пользователя; рассылок на группу нет."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Относительный путь фронта, куда ведёт клик; абсолютный URL для внешних
    # каналов собирается из NOTIFY__PUBLIC_URL
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # NULL — непрочитанное; шторка проставляет время при открытии
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Шторка читает ленту одного пользователя в обратном хронологическом порядке
        Index("ix_notifications_user_created", "user_id", created_at.desc()),
    )


class UserChannel(Base):
    """Привязка канала доставки к пользователю."""

    __tablename__ = "user_channels"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    # Для телеграма — chat_id строкой; в ответах API маскируется
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    # Тумблер «слать сюда», отдельно от факта привязки
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "channel", name="uq_user_channels_user_channel"),
    )


class ChannelLinkToken(Base):
    """Одноразовый токен привязки канала.

    Лежит в БД, а не в памяти процесса: в деве бэкенд поднят с --reload, и правка
    любого файла убила бы токен посреди привязки.
    """

    __tablename__ = "channel_link_tokens"

    token: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 4: Подключить модели к Alembic**

В `backend/app/models.py` добавить импорт в алфавитном порядке (после `methodology`):

```python
from app.domains.notification import models as notification_models  # noqa: F401
```

- [ ] **Step 5: Запустить тест и убедиться, что проходит**

Run: `cd backend && uv run pytest tests/test_notification_model.py -v`
Expected: PASS, 5 passed

- [ ] **Step 6: Сгенерировать миграцию**

```bash
cd /Users/fadegor05/codes/LCT-7
docker compose --project-directory . --env-file ./.env --env-file ./deploy/versions.env \
  -f deploy/docker/common/core.yaml -f deploy/docker/common/infra.yaml \
  -f deploy/docker/dev/core.yaml \
  exec backend alembic revision --autogenerate -m "notifications: уведомления, каналы и токены привязки"
```

Открыть получившийся файл в `backend/alembic/versions/` и проверить глазами: в нём должны быть три `op.create_table` и ни одного `sa.Enum` — если автогенерация выдала `sa.Enum`, заменить на `sa.String(...)` вручную. Убедиться, что `down_revision = "0012"`.

- [ ] **Step 7: Проверить, что миграция накатывается и откатывается**

```bash
cd /Users/fadegor05/codes/LCT-7
docker compose --project-directory . --env-file ./.env --env-file ./deploy/versions.env \
  -f deploy/docker/common/core.yaml -f deploy/docker/common/infra.yaml \
  -f deploy/docker/dev/core.yaml exec backend alembic upgrade head
docker compose --project-directory . --env-file ./.env --env-file ./deploy/versions.env \
  -f deploy/docker/common/core.yaml -f deploy/docker/common/infra.yaml \
  -f deploy/docker/dev/core.yaml exec backend alembic downgrade -1
docker compose --project-directory . --env-file ./.env --env-file ./deploy/versions.env \
  -f deploy/docker/common/core.yaml -f deploy/docker/common/infra.yaml \
  -f deploy/docker/dev/core.yaml exec backend alembic upgrade head
```

Expected: все три команды завершаются без ошибок.

- [ ] **Step 8: Закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make pretty && make check
git add backend/app/domains/notification backend/app/models.py backend/alembic/versions backend/tests/test_notification_model.py
git commit -m "feat(backend): таблицы уведомлений, каналов и токенов привязки"
```

---

## Task 3: Репозитории и сервис ленты

**Files:**
- Create: `backend/app/domains/notification/repository.py`
- Create: `backend/app/domains/notification/schemas.py`
- Create: `backend/app/domains/notification/dispatcher.py`
- Create: `backend/app/domains/notification/service.py`
- Test: `backend/tests/test_notification_service.py`

**Interfaces:**
- Consumes: `Notification`, `UserChannel`, `ChannelLinkToken`, `NotificationType`, `ChannelKind` (Task 2)
- Produces:
  - `NotificationRepository.list_for_user(user_id, limit, offset) -> Sequence[Notification]`
  - `NotificationRepository.count_unread(user_id) -> int`
  - `NotificationRepository.mark_all_read(user_id, now) -> int`
  - `UserChannelRepository.list_for_user(user_id) -> Sequence[UserChannel]`
  - `UserChannelRepository.get_for(user_id, channel) -> UserChannel | None`
  - `UserChannelRepository.list_enabled(user_id) -> Sequence[UserChannel]`
  - `ChannelLinkTokenRepository` (только унаследованные методы)
  - `NotificationDispatcher` Protocol со `schedule(notification_id: uuid.UUID) -> None`; `NullDispatcher`
  - `NotificationService.notify(...) -> Notification`, `.list_for(...) -> NotificationList`, `.mark_all_read(user_id) -> int`
  - Схемы `NotificationRead`, `NotificationList`, `UserChannelRead`, `ChannelToggle`, `ChannelLinkResponse`, `TestNotificationRequest`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_notification_service.py`:

```python
"""Лента уведомлений: порядок, счётчик непрочитанных, пометка прочитанным."""

import uuid

from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notification.dispatcher import NotificationDispatcher
from app.domains.notification.models import NotificationType
from app.domains.notification.repository import NotificationRepository
from app.domains.notification.service import NotificationService
from app.domains.user.models import User
from app.domains.user.service import STAND_USER_ID, UserService


class RecordingDispatcher:
    """Запоминает, что отправку попросили, но ничего не шлёт."""

    def __init__(self) -> None:
        self.scheduled: list[uuid.UUID] = []

    def schedule(self, notification_id: uuid.UUID) -> None:
        self.scheduled.append(notification_id)


async def make_service(
    container: AsyncContainer, dispatcher: NotificationDispatcher
) -> tuple[NotificationService, AsyncSession]:
    request_container = container()
    session = await request_container.get(AsyncSession)
    service = NotificationService(
        repository=NotificationRepository(session),
        session=session,
        dispatcher=dispatcher,
    )
    return service, session


async def seed_user(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


async def test_notify_stores_and_schedules_delivery(container: AsyncContainer) -> None:
    await seed_user(container)
    dispatcher = RecordingDispatcher()
    service, _ = await make_service(container, dispatcher)

    created = await service.notify(
        user_id=STAND_USER_ID,
        type=NotificationType.SYSTEM,
        title="Заголовок",
        body="Текст",
        link="/sites",
    )

    assert created.read_at is None
    assert dispatcher.scheduled == [created.id]


async def test_list_returns_newest_first_with_unread_count(container: AsyncContainer) -> None:
    await seed_user(container)
    service, _ = await make_service(container, RecordingDispatcher())
    await service.notify(STAND_USER_ID, NotificationType.SYSTEM, "Первое", "a", None)
    await service.notify(STAND_USER_ID, NotificationType.SYSTEM, "Второе", "b", None)

    page = await service.list_for(STAND_USER_ID, limit=50, offset=0)

    assert [item.title for item in page.items] == ["Второе", "Первое"]
    assert page.unread_count == 2


async def test_mark_all_read_zeroes_the_counter(container: AsyncContainer) -> None:
    await seed_user(container)
    service, _ = await make_service(container, RecordingDispatcher())
    await service.notify(STAND_USER_ID, NotificationType.SYSTEM, "Первое", "a", None)

    marked = await service.mark_all_read(STAND_USER_ID)
    page = await service.list_for(STAND_USER_ID, limit=50, offset=0)

    assert marked == 1
    assert page.unread_count == 0
    assert page.items[0].read_at is not None


async def test_mark_all_read_is_idempotent(container: AsyncContainer) -> None:
    """Открыли шторку дважды — второй раз помечать нечего."""
    await seed_user(container)
    service, _ = await make_service(container, RecordingDispatcher())
    await service.notify(STAND_USER_ID, NotificationType.SYSTEM, "Первое", "a", None)

    first = await service.mark_all_read(STAND_USER_ID)
    second = await service.mark_all_read(STAND_USER_ID)

    assert (first, second) == (1, 0)


async def test_mark_all_read_does_not_touch_other_users(container: AsyncContainer) -> None:
    """Review Focus 1: пометка прочитанным изолирована по пользователю."""
    await seed_user(container)
    other_id = uuid.uuid4()
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(User(id=other_id, full_name="Другой инженер"))
        await session.commit()

    service, _ = await make_service(container, RecordingDispatcher())
    await service.notify(STAND_USER_ID, NotificationType.SYSTEM, "Моё", "a", None)
    await service.notify(other_id, NotificationType.SYSTEM, "Чужое", "b", None)

    await service.mark_all_read(STAND_USER_ID)
    mine = await service.list_for(STAND_USER_ID, limit=50, offset=0)
    theirs = await service.list_for(other_id, limit=50, offset=0)

    assert mine.unread_count == 0
    assert theirs.unread_count == 1


async def test_list_paginates(container: AsyncContainer) -> None:
    await seed_user(container)
    service, _ = await make_service(container, RecordingDispatcher())
    for index in range(3):
        await service.notify(STAND_USER_ID, NotificationType.SYSTEM, f"№{index}", "x", None)

    page = await service.list_for(STAND_USER_ID, limit=2, offset=0)
    tail = await service.list_for(STAND_USER_ID, limit=2, offset=2)

    assert len(page.items) == 2
    assert len(tail.items) == 1
    # Счётчик непрочитанных считает всё, а не страницу
    assert page.unread_count == 3
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd backend && uv run pytest tests/test_notification_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domains.notification.repository'`

- [ ] **Step 3: Реализовать схемы**

Создать `backend/app/domains/notification/schemas.py`:

```python
"""Pydantic-схемы уведомлений и каналов доставки."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.notification.models import ChannelKind, NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    title: str
    body: str
    link: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationList(BaseModel):
    """Страница ленты. unread_count считает всю ленту, а не выданную страницу."""

    items: list[NotificationRead]
    unread_count: int


class MarkReadResponse(BaseModel):
    marked: int


class UserChannelRead(BaseModel):
    """Привязка канала. Полный адрес наружу не отдаётся."""

    channel: ChannelKind
    address_masked: str
    enabled: bool
    linked_at: datetime


class ChannelToggle(BaseModel):
    enabled: bool


class ChannelLinkResponse(BaseModel):
    """Ссылка привязки и срок её жизни."""

    url: str
    expires_at: datetime


class TestNotificationRequest(BaseModel):
    """Служебное создание уведомления себе — для демо и ручной проверки."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(default="Тестовое уведомление", min_length=1, max_length=255)
    body: str = Field(default="Проверка системы уведомлений", min_length=1, max_length=4000)
    type: NotificationType = NotificationType.SYSTEM
    link: str | None = Field(default=None, max_length=500)
```

- [ ] **Step 4: Реализовать репозитории**

Создать `backend/app/domains/notification/repository.py`:

```python
"""Репозитории уведомлений и каналов. Коммит — забота сервиса."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, update

from app.core.repository import BaseRepository
from app.domains.notification.models import (
    ChannelKind,
    ChannelLinkToken,
    Notification,
    UserChannel,
)


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def list_for_user(
        self, user_id: uuid.UUID, limit: int, offset: int
    ) -> Sequence[Notification]:
        """Лента пользователя, новые сверху."""
        result = await self._session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def count_unread(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        return int(result.scalar_one())

    async def mark_all_read(self, user_id: uuid.UUID, now: datetime) -> int:
        """Пометить прочитанными все непрочитанные этого пользователя; сколько тронули."""
        result = await self._session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=now)
        )
        await self._session.flush()
        return int(result.rowcount or 0)


class UserChannelRepository(BaseRepository[UserChannel]):
    model = UserChannel

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[UserChannel]:
        result = await self._session.execute(
            select(UserChannel)
            .where(UserChannel.user_id == user_id)
            .order_by(UserChannel.channel)
        )
        return result.scalars().all()

    async def get_for(self, user_id: uuid.UUID, channel: ChannelKind) -> UserChannel | None:
        result = await self._session.execute(
            select(UserChannel).where(
                UserChannel.user_id == user_id, UserChannel.channel == channel.value
            )
        )
        return result.scalar_one_or_none()

    async def list_enabled(self, user_id: uuid.UUID) -> Sequence[UserChannel]:
        result = await self._session.execute(
            select(UserChannel).where(
                UserChannel.user_id == user_id, UserChannel.enabled.is_(True)
            )
        )
        return result.scalars().all()


class ChannelLinkTokenRepository(BaseRepository[ChannelLinkToken]):
    model = ChannelLinkToken
```

- [ ] **Step 5: Реализовать диспетчер-заглушку**

Создать `backend/app/domains/notification/dispatcher.py`:

```python
"""Шов доставки: сервис уведомлений просит отправить, не зная как.

Настоящая реализация (BackgroundDispatcher) появляется в задаче про доставку;
здесь интерфейс и пустышка, с которой работают тесты сервиса.
"""

import uuid
from typing import Protocol


class NotificationDispatcher(Protocol):
    """Планировщик доставки. Синхронный: вызывается из уже закоммиченного сервиса."""

    def schedule(self, notification_id: uuid.UUID) -> None:
        """Запланировать доставку уведомления по привязанным каналам."""
        ...


class NullDispatcher:
    """Ничего не доставляет. Умолчание, когда каналы не настроены."""

    def schedule(self, notification_id: uuid.UUID) -> None:
        return None
```

- [ ] **Step 6: Реализовать сервис**

Создать `backend/app/domains/notification/service.py`:

```python
"""Лента уведомлений: создание, чтение, пометка прочитанным."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notification.dispatcher import NotificationDispatcher
from app.domains.notification.models import Notification, NotificationType
from app.domains.notification.repository import NotificationRepository
from app.domains.notification.schemas import NotificationList, NotificationRead


class NotificationService:
    def __init__(
        self,
        repository: NotificationRepository,
        session: AsyncSession,
        dispatcher: NotificationDispatcher,
    ) -> None:
        self._repository = repository
        self._session = session
        self._dispatcher = dispatcher

    async def notify(
        self,
        user_id: uuid.UUID,
        type: NotificationType,
        title: str,
        body: str,
        link: str | None = None,
    ) -> Notification:
        """Создать уведомление и запланировать доставку по каналам.

        Единственная точка входа для доменов-источников: они не знают ни про
        каналы, ни про телеграм.
        """
        notification = Notification(
            user_id=user_id,
            type=type.value,
            title=title,
            body=body,
            link=link,
        )
        await self._repository.add(notification)
        await self._session.commit()
        # Доставка идёт только после коммита: до него уведомления ещё нет
        self._dispatcher.schedule(notification.id)
        return notification

    async def list_for(self, user_id: uuid.UUID, limit: int, offset: int) -> NotificationList:
        items = await self._repository.list_for_user(user_id, limit=limit, offset=offset)
        unread = await self._repository.count_unread(user_id)
        return NotificationList(
            items=[NotificationRead.model_validate(item) for item in items],
            unread_count=unread,
        )

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        """Пометить прочитанным всё непрочитанное; сколько записей тронули."""
        marked = await self._repository.mark_all_read(user_id, datetime.now(UTC))
        await self._session.commit()
        return marked
```

- [ ] **Step 7: Запустить тесты и убедиться, что проходят**

Run: `cd backend && uv run pytest tests/test_notification_service.py -v`
Expected: PASS, 6 passed

- [ ] **Step 8: Закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make pretty && make check
git add backend/app/domains/notification backend/tests/test_notification_service.py
git commit -m "feat(backend): сервис ленты уведомлений"
```

---

## Task 4: Роуты ленты и DI

**Files:**
- Create: `backend/app/domains/notification/router.py`
- Create: `backend/app/domains/notification/provider.py`
- Modify: `backend/app/plugins/di.py`
- Modify: `backend/app/plugins/routing.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_notification_router.py`

**Interfaces:**
- Consumes: `NotificationService` (Task 3), `CurrentUser` из `app.domains.user.provider`
- Produces: `NotificationProvider`; роуты `GET /notifications`, `POST /notifications/read`, `POST /notifications/test`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_notification_router.py`:

```python
"""HTTP-контракт ленты уведомлений."""

from dishka import AsyncContainer
from httpx import AsyncClient

from app.domains.user.service import UserService


async def seed(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


async def test_empty_feed(client: AsyncClient, container: AsyncContainer) -> None:
    await seed(container)

    response = await client.get("/notifications")

    assert response.status_code == 200
    assert response.json() == {"items": [], "unread_count": 0}


async def test_test_endpoint_creates_notification(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed(container)

    created = await client.post("/notifications/test", json={})
    feed = await client.get("/notifications")

    assert created.status_code == 201
    assert feed.json()["unread_count"] == 1
    assert feed.json()["items"][0]["title"] == "Тестовое уведомление"


async def test_test_endpoint_accepts_custom_text(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed(container)

    await client.post(
        "/notifications/test",
        json={"title": "Отклонение", "body": "Нет экскаватора", "link": "/sites"},
    )
    feed = await client.get("/notifications")

    item = feed.json()["items"][0]
    assert (item["title"], item["body"], item["link"]) == (
        "Отклонение",
        "Нет экскаватора",
        "/sites",
    )


async def test_read_marks_everything(client: AsyncClient, container: AsyncContainer) -> None:
    await seed(container)
    await client.post("/notifications/test", json={})
    await client.post("/notifications/test", json={})

    marked = await client.post("/notifications/read")
    feed = await client.get("/notifications")

    assert marked.status_code == 200
    assert marked.json() == {"marked": 2}
    assert feed.json()["unread_count"] == 0


async def test_notification_fields_are_exactly_the_contract(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Фронт валидирует ответ zod-схемой — лишние и недостающие поля ломают экран."""
    await seed(container)
    await client.post("/notifications/test", json={})

    item = (await client.get("/notifications")).json()["items"][0]

    assert set(item) == {"id", "type", "title", "body", "link", "read_at", "created_at"}


async def test_limit_is_capped(client: AsyncClient, container: AsyncContainer) -> None:
    """limit приходит из строки запроса — выпрашивать миллион записей нельзя."""
    await seed(container)

    response = await client.get("/notifications", params={"limit": 10_000})

    assert response.status_code == 422
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd backend && uv run pytest tests/test_notification_router.py -v`
Expected: FAIL — все шесть падают на 404, роутов ещё нет

- [ ] **Step 3: Реализовать провайдер**

Создать `backend/app/domains/notification/provider.py`:

```python
"""DI-провайдеры домена notification."""

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notification.dispatcher import NotificationDispatcher, NullDispatcher
from app.domains.notification.repository import (
    ChannelLinkTokenRepository,
    NotificationRepository,
    UserChannelRepository,
)
from app.domains.notification.service import NotificationService


class NotificationProvider(Provider):
    scope = Scope.REQUEST

    notifications = provide(NotificationRepository)
    channels = provide(UserChannelRepository)
    tokens = provide(ChannelLinkTokenRepository)

    @provide(scope=Scope.REQUEST)
    def service(
        self,
        repository: NotificationRepository,
        session: AsyncSession,
        dispatcher: NotificationDispatcher,
    ) -> NotificationService:
        return NotificationService(repository, session, dispatcher)


class NullDispatcherProvider(Provider):
    """Доставки нет. Переопределяется провайдером каналов, когда они настроены."""

    scope = Scope.APP

    @provide
    def dispatcher(self) -> NotificationDispatcher:
        return NullDispatcher()
```

- [ ] **Step 4: Реализовать роутер**

Создать `backend/app/domains/notification/router.py`:

```python
"""HTTP-роуты ленты уведомлений текущего пользователя."""

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Query

from app.domains.notification.schemas import (
    MarkReadResponse,
    NotificationList,
    NotificationRead,
    TestNotificationRequest,
)
from app.domains.notification.service import NotificationService
from app.domains.user.provider import CurrentUser

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
@inject
async def list_notifications(
    user: FromDishka[CurrentUser],
    service: FromDishka[NotificationService],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NotificationList:
    return await service.list_for(user.id, limit=limit, offset=offset)


@router.post("/read")
@inject
async def mark_all_read(
    user: FromDishka[CurrentUser],
    service: FromDishka[NotificationService],
) -> MarkReadResponse:
    """Открытие шторки помечает прочитанным всё непрочитанное разом."""
    return MarkReadResponse(marked=await service.mark_all_read(user.id))


@router.post("/test", status_code=201)
@inject
async def create_test_notification(
    data: TestNotificationRequest,
    user: FromDishka[CurrentUser],
    service: FromDishka[NotificationService],
) -> NotificationRead:
    """Служебное создание уведомления себе: источников событий пока нет."""
    created = await service.notify(
        user_id=user.id,
        type=data.type,
        title=data.title,
        body=data.body,
        link=data.link,
    )
    return NotificationRead.model_validate(created)
```

- [ ] **Step 5: Подключить к DI и роутингу**

В `backend/app/plugins/di.py` добавить импорт:

```python
from app.domains.notification.provider import NotificationProvider, NullDispatcherProvider
```

и в `create_container()` после `MethodologyProvider(),`:

```python
        NotificationProvider(),
        NullDispatcherProvider(),
```

В `backend/app/plugins/routing.py` добавить импорт:

```python
from app.domains.notification.router import router as notification_router
```

и строку в блок защищённых роутов:

```python
api_router.include_router(notification_router, dependencies=[Depends(require_auth)])
```

В `backend/tests/conftest.py` добавить те же импорты и те же две строки в `_make_container()` — иначе тестовый контейнер не разрешит `NotificationService`.

- [ ] **Step 6: Запустить тесты и убедиться, что проходят**

Run: `cd backend && uv run pytest tests/test_notification_router.py -v`
Expected: PASS, 6 passed

- [ ] **Step 7: Прогнать весь бэкенд и закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make test && make pretty && make check
git add backend/app/domains/notification backend/app/plugins backend/tests
git commit -m "feat(backend): роуты ленты уведомлений"
```

---

## Task 5: Интерфейс канала и лог-адаптер

**Files:**
- Create: `backend/app/adapters/notify/__init__.py` (пустой)
- Create: `backend/app/adapters/notify/base.py`
- Create: `backend/app/adapters/notify/log.py`
- Create: `backend/app/adapters/notify/factory.py`
- Test: `backend/tests/test_notify_channels.py`

**Interfaces:**
- Consumes: `ChannelKind` (Task 2), `NotifySettings` (Task 1)
- Produces:
  - `ChannelMessage(title: str, body: str, link: str | None)`
  - `NotifyError`
  - `NotificationChannel` Protocol: `kind: ClassVar[ChannelKind]`, `async send(address: str, message: ChannelMessage) -> None`
  - `ChannelRegistry` — `dict[ChannelKind, NotificationChannel]` с методом `get(kind) -> NotificationChannel | None`
  - `create_channel_registry(settings: Settings) -> ChannelRegistry`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_notify_channels.py`:

```python
"""Реестр каналов: без настроек — только запись в лог."""

import logging

import pytest

from app.adapters.notify.base import ChannelMessage, NotificationChannel
from app.adapters.notify.factory import create_channel_registry
from app.adapters.notify.log import LogChannel
from app.core.settings import Settings
from app.domains.notification.models import ChannelKind


def test_log_channel_satisfies_the_protocol() -> None:
    channel: NotificationChannel = LogChannel()

    assert channel.kind is ChannelKind.TELEGRAM


async def test_log_channel_writes_title_and_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    channel = LogChannel()

    with caplog.at_level(logging.INFO):
        await channel.send("42", ChannelMessage(title="Заголовок", body="Текст", link=None))

    assert "Заголовок" in caplog.text


async def test_registry_without_token_falls_back_to_log() -> None:
    """Без токена бота привязанный телеграм не должен ронять доставку."""
    settings = Settings()
    settings.notify.telegram.token = None

    registry = create_channel_registry(settings)

    assert isinstance(registry.get(ChannelKind.TELEGRAM), LogChannel)


def test_registry_returns_none_for_unknown_channel() -> None:
    settings = Settings()

    registry = create_channel_registry(settings)

    assert registry.get("smoke-signals") is None  # type: ignore[arg-type]
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd backend && uv run pytest tests/test_notify_channels.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.adapters.notify'`

- [ ] **Step 3: Реализовать интерфейс**

Создать пустой `backend/app/adapters/notify/__init__.py` и `backend/app/adapters/notify/base.py`:

```python
"""Базовые интерфейсы доставки уведомлений по внешним каналам.

Устроено как adapters/storage: Protocol здесь, реализации рядом, сборка в factory.
Добавить канал = один файл плюс строка в фабрике.
"""

from typing import ClassVar, Protocol

from pydantic import BaseModel

from app.domains.notification.models import ChannelKind


class NotifyError(Exception):
    """Ошибка доставки. Ловится диспетчером и пишется в лог."""


class ChannelMessage(BaseModel):
    """Сообщение в терминах канала: адаптер сам решает, как его подать."""

    title: str
    body: str
    # Абсолютный URL; относительный путь во внешнем канале бесполезен
    link: str | None = None


class NotificationChannel(Protocol):
    """Канал доставки одному адресату."""

    kind: ClassVar[ChannelKind]

    async def send(self, address: str, message: ChannelMessage) -> None:
        """Отправить сообщение по адресу канала.

        Raises:
            NotifyError: При любой ошибке доставки.
        """
        ...
```

- [ ] **Step 4: Реализовать лог-канал и фабрику**

Создать `backend/app/adapters/notify/log.py`:

```python
"""Канал-заглушка: пишет сообщение в лог приложения.

Умолчание, когда внешний канал не настроен, и то, с чем работают тесты.
"""

import logging
from typing import ClassVar

from app.adapters.notify.base import ChannelMessage
from app.domains.notification.models import ChannelKind

logger = logging.getLogger(__name__)


class LogChannel:
    """Ничего никуда не шлёт, только протоколирует попытку."""

    kind: ClassVar[ChannelKind] = ChannelKind.TELEGRAM

    async def send(self, address: str, message: ChannelMessage) -> None:
        logger.info(
            "Уведомление не отправлено (канал не настроен): адрес=%s, заголовок=%s, текст=%s",
            address,
            message.title,
            message.body,
        )
```

Создать `backend/app/adapters/notify/factory.py`:

```python
"""Сборка реестра каналов по настройкам."""

from app.adapters.notify.base import NotificationChannel
from app.adapters.notify.log import LogChannel
from app.core.settings import Settings
from app.domains.notification.models import ChannelKind


class ChannelRegistry:
    """Канал по его виду. Неизвестный вид — None, доставка просто не состоится."""

    def __init__(self, channels: dict[ChannelKind, NotificationChannel]) -> None:
        self._channels = channels

    def get(self, kind: ChannelKind) -> NotificationChannel | None:
        return self._channels.get(kind)


def create_channel_registry(settings: Settings) -> ChannelRegistry:
    """Собрать реестр: настоящий телеграм при заданном токене, иначе лог."""
    channels: dict[ChannelKind, NotificationChannel] = {ChannelKind.TELEGRAM: LogChannel()}
    return ChannelRegistry(channels)
```

Настоящий телеграм подключается к фабрике в следующей задаче.

- [ ] **Step 5: Запустить тесты и убедиться, что проходят**

Run: `cd backend && uv run pytest tests/test_notify_channels.py -v`
Expected: PASS, 4 passed

- [ ] **Step 6: Закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make pretty && make check
git add backend/app/adapters/notify backend/tests/test_notify_channels.py
git commit -m "feat(backend): интерфейс каналов доставки и лог-адаптер"
```

---

## Task 6: Телеграм-клиент и канал

**Files:**
- Create: `backend/app/adapters/notify/telegram.py`
- Modify: `backend/app/adapters/notify/factory.py`
- Test: `backend/tests/test_notify_telegram.py`

**Interfaces:**
- Consumes: `ChannelMessage`, `NotifyError`, `ChannelRegistry` (Task 5), `TelegramSettings` (Task 1)
- Produces:
  - `TelegramClient(token: str, timeout_s: float)` с `async send_message(chat_id: str, text: str) -> None` и `async get_updates(offset: int | None, timeout_s: int) -> list[dict]`
  - `TelegramChannel(client: TelegramClient)` — реализация `NotificationChannel`
  - `TELEGRAM_TEXT_LIMIT = 4096`
  - `format_message(message: ChannelMessage) -> str`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_notify_telegram.py`:

```python
"""Телеграм как канал доставки: формат текста, лимит, ошибки."""

import pytest

from app.adapters.notify.base import ChannelMessage, NotifyError
from app.adapters.notify.telegram import (
    TELEGRAM_TEXT_LIMIT,
    TelegramChannel,
    format_message,
)
from app.domains.notification.models import ChannelKind


class FakeTelegramClient:
    """Вместо сети — список отправленного."""

    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list[tuple[str, str]] = []
        self.error = error

    async def send_message(self, chat_id: str, text: str) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append((chat_id, text))


def test_format_includes_title_body_and_link() -> None:
    text = format_message(
        ChannelMessage(title="Отклонение", body="Нет экскаватора", link="https://x/y")
    )

    assert "Отклонение" in text
    assert "Нет экскаватора" in text
    assert "https://x/y" in text


def test_format_without_link_has_no_dangling_separator() -> None:
    text = format_message(ChannelMessage(title="Заголовок", body="Текст", link=None))

    assert text.strip() == text
    assert text.endswith("Текст")


def test_format_truncates_at_telegram_limit() -> None:
    """Review Focus 4: длинный текст обрезается, а не роняет отправку."""
    text = format_message(ChannelMessage(title="Т", body="я" * 10_000, link=None))

    assert len(text) <= TELEGRAM_TEXT_LIMIT
    assert text.endswith("…")


async def test_channel_sends_to_chat_id() -> None:
    client = FakeTelegramClient()
    channel = TelegramChannel(client)  # type: ignore[arg-type]

    await channel.send("12345", ChannelMessage(title="Заголовок", body="Текст", link=None))

    assert client.sent[0][0] == "12345"
    assert "Заголовок" in client.sent[0][1]


async def test_channel_wraps_transport_errors() -> None:
    """Review Focus 3: бот заблокирован — наружу уходит NotifyError, не httpx-ошибка."""
    client = FakeTelegramClient(error=RuntimeError("403 Forbidden: bot was blocked by the user"))
    channel = TelegramChannel(client)  # type: ignore[arg-type]

    with pytest.raises(NotifyError):
        await channel.send("12345", ChannelMessage(title="Т", body="Б", link=None))


def test_channel_declares_its_kind() -> None:
    assert TelegramChannel.kind == ChannelKind.TELEGRAM
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd backend && uv run pytest tests/test_notify_telegram.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.adapters.notify.telegram'`

- [ ] **Step 3: Реализовать клиент и канал**

Создать `backend/app/adapters/notify/telegram.py`:

```python
"""Телеграм: тонкий клиент Bot API и канал доставки поверх него.

Единственное место в проекте, знающее про формат Bot API. Токен в логи не пишется.
"""

import logging
from typing import Any, ClassVar

import httpx

from app.adapters.notify.base import ChannelMessage, NotifyError
from app.domains.notification.models import ChannelKind

logger = logging.getLogger(__name__)

# Жёсткий лимит одного сообщения в Bot API
TELEGRAM_TEXT_LIMIT = 4096


def format_message(message: ChannelMessage) -> str:
    """Собрать текст сообщения и обрезать до лимита Bot API.

    Разметка не используется намеренно: заголовки уведомлений приходят из доменов
    и могут содержать символы, которые пришлось бы экранировать.
    """
    parts = [message.title, "", message.body]
    if message.link:
        parts += ["", message.link]
    text = "\n".join(parts)
    if len(text) > TELEGRAM_TEXT_LIMIT:
        text = text[: TELEGRAM_TEXT_LIMIT - 1] + "…"
    return text


class TelegramClient:
    """Обёртка над Bot API. Создаётся один раз на приложение."""

    def __init__(self, token: str, timeout_s: float = 35.0) -> None:
        self._token = token
        self._timeout_s = timeout_s

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._token}/{method}"

    async def send_message(self, chat_id: str, text: str) -> None:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.post(
                self._url("sendMessage"),
                json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            )
        if response.status_code != 200:
            # Тело содержит описание ошибки Bot API, но не токен — его нет в ответе
            raise NotifyError(f"Telegram sendMessage {response.status_code}: {response.text}")

    async def get_updates(self, offset: int | None, timeout_s: int) -> list[dict[str, Any]]:
        """Long polling. Телеграм держит соединение, пока не появится апдейт."""
        params: dict[str, Any] = {"timeout": timeout_s}
        if offset is not None:
            params["offset"] = offset
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(self._url("getUpdates"), params=params)
        if response.status_code != 200:
            raise NotifyError(f"Telegram getUpdates {response.status_code}")
        payload = response.json()
        if not payload.get("ok"):
            raise NotifyError("Telegram getUpdates вернул ok=false")
        return list(payload.get("result", []))


class TelegramChannel:
    """Доставка уведомления в телеграм-чат."""

    kind: ClassVar[ChannelKind] = ChannelKind.TELEGRAM

    def __init__(self, client: TelegramClient) -> None:
        self._client = client

    async def send(self, address: str, message: ChannelMessage) -> None:
        try:
            await self._client.send_message(address, format_message(message))
        except NotifyError:
            raise
        except Exception as error:  # httpx, таймауты, разбор JSON
            raise NotifyError(f"Не удалось отправить в телеграм: {error}") from error
```

- [ ] **Step 4: Подключить телеграм к фабрике**

Переписать `create_channel_registry` в `backend/app/adapters/notify/factory.py`:

```python
def create_channel_registry(settings: Settings) -> ChannelRegistry:
    """Собрать реестр: настоящий телеграм при заданном токене, иначе лог."""
    telegram: NotificationChannel = LogChannel()
    if settings.notify.telegram.token:
        telegram = TelegramChannel(
            TelegramClient(
                token=settings.notify.telegram.token,
                timeout_s=settings.notify.telegram.request_timeout_s,
            )
        )
    channels: dict[ChannelKind, NotificationChannel] = {ChannelKind.TELEGRAM: telegram}
    return ChannelRegistry(channels)
```

и добавить импорт:

```python
from app.adapters.notify.telegram import TelegramChannel, TelegramClient
```

- [ ] **Step 5: Дописать тест фабрики**

Добавить в `backend/tests/test_notify_channels.py`:

```python
async def test_registry_with_token_uses_real_telegram() -> None:
    from app.adapters.notify.telegram import TelegramChannel

    settings = Settings()
    settings.notify.telegram.token = "123:abc"

    registry = create_channel_registry(settings)

    assert isinstance(registry.get(ChannelKind.TELEGRAM), TelegramChannel)
```

- [ ] **Step 6: Запустить тесты и убедиться, что проходят**

Run: `cd backend && uv run pytest tests/test_notify_telegram.py tests/test_notify_channels.py -v`
Expected: PASS, 11 passed

- [ ] **Step 7: Закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make pretty && make check
git add backend/app/adapters/notify backend/tests/test_notify_telegram.py backend/tests/test_notify_channels.py
git commit -m "feat(backend): телеграм как канал доставки"
```

---

## Task 7: Доставка уведомлений

**Files:**
- Modify: `backend/app/domains/notification/dispatcher.py`
- Modify: `backend/app/domains/notification/provider.py`
- Modify: `backend/app/plugins/di.py`
- Test: `backend/tests/test_notification_dispatcher.py`

**Interfaces:**
- Consumes: `ChannelRegistry` (Task 5), `NotificationRepository`, `UserChannelRepository` (Task 3), `NotifySettings` (Task 1)
- Produces: `BackgroundDispatcher(maker, registry, settings)` с `schedule(notification_id) -> None` и `async deliver(notification_id) -> int` (сколько каналов успешно приняли); `ChannelsProvider`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_notification_dispatcher.py`:

```python
"""Доставка уведомления по привязанным каналам."""

import logging
import uuid

import pytest
from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.notify.base import ChannelMessage, NotifyError
from app.adapters.notify.factory import ChannelRegistry
from app.core.settings import Settings
from app.domains.notification.dispatcher import BackgroundDispatcher
from app.domains.notification.models import (
    ChannelKind,
    Notification,
    NotificationType,
    UserChannel,
)
from app.domains.notification.repository import UserChannelRepository
from app.domains.user.service import STAND_USER_ID, UserService


class SpyChannel:
    kind = ChannelKind.TELEGRAM

    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list[tuple[str, ChannelMessage]] = []
        self.error = error

    async def send(self, address: str, message: ChannelMessage) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append((address, message))


async def seed(container: AsyncContainer, *, enabled: bool = True) -> uuid.UUID:
    """Пользователь, привязанный телеграм и одно уведомление; вернуть его id."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()
        session = await request_container.get(AsyncSession)
        session.add(
            UserChannel(
                user_id=STAND_USER_ID,
                channel=ChannelKind.TELEGRAM,
                address="424242",
                enabled=enabled,
            )
        )
        notification = Notification(
            user_id=STAND_USER_ID,
            type=NotificationType.SYSTEM,
            title="Отклонение",
            body="Нет экскаватора",
            link="/sites/1",
        )
        session.add(notification)
        await session.commit()
        return notification.id


def make_dispatcher(
    maker: async_sessionmaker[AsyncSession], channel: SpyChannel
) -> BackgroundDispatcher:
    settings = Settings()
    settings.notify.public_url = "https://stand.example"
    return BackgroundDispatcher(
        maker=maker,
        registry=ChannelRegistry({ChannelKind.TELEGRAM: channel}),  # type: ignore[dict-item]
        settings=settings,
    )


async def test_delivers_to_enabled_channel(container: AsyncContainer) -> None:
    notification_id = await seed(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    channel = SpyChannel()

    delivered = await make_dispatcher(maker, channel).deliver(notification_id)

    assert delivered == 1
    assert channel.sent[0][0] == "424242"
    assert channel.sent[0][1].title == "Отклонение"


async def test_relative_link_becomes_absolute(container: AsyncContainer) -> None:
    """В телеграме относительный путь бесполезен."""
    notification_id = await seed(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    channel = SpyChannel()

    await make_dispatcher(maker, channel).deliver(notification_id)

    assert channel.sent[0][1].link == "https://stand.example/sites/1"


async def test_disabled_channel_is_skipped(container: AsyncContainer) -> None:
    notification_id = await seed(container, enabled=False)
    maker = await container.get(async_sessionmaker[AsyncSession])
    channel = SpyChannel()

    delivered = await make_dispatcher(maker, channel).deliver(notification_id)

    assert delivered == 0
    assert channel.sent == []


async def test_channel_failure_is_logged_and_swallowed(
    container: AsyncContainer, caplog: pytest.LogCaptureFixture
) -> None:
    """Review Focus 3: бот заблокирован — доставка молчит в лог, привязка цела."""
    notification_id = await seed(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    channel = SpyChannel(error=NotifyError("403 bot was blocked"))

    with caplog.at_level(logging.WARNING):
        delivered = await make_dispatcher(maker, channel).deliver(notification_id)

    assert delivered == 0
    assert "403" in caplog.text

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        # Привязка не удаляется из-за неудачной отправки
        still_linked = await UserChannelRepository(session).get_for(
            STAND_USER_ID, ChannelKind.TELEGRAM
        )
        assert still_linked is not None
        assert still_linked.enabled is True


async def test_missing_notification_is_not_an_error(container: AsyncContainer) -> None:
    """Транзакция откатилась — доставлять нечего, падать нельзя."""
    await seed(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    channel = SpyChannel()

    delivered = await make_dispatcher(maker, channel).deliver(uuid.uuid4())

    assert delivered == 0
    assert channel.sent == []
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd backend && uv run pytest tests/test_notification_dispatcher.py -v`
Expected: FAIL — `ImportError: cannot import name 'BackgroundDispatcher'`

- [ ] **Step 3: Реализовать диспетчер**

Дописать в `backend/app/domains/notification/dispatcher.py` (импорты вверх файла):

```python
import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.notify.base import ChannelMessage
from app.adapters.notify.factory import ChannelRegistry
from app.core.settings import Settings
from app.domains.notification.models import ChannelKind
from app.domains.notification.repository import NotificationRepository, UserChannelRepository

logger = logging.getLogger(__name__)
```

и класс:

```python
class BackgroundDispatcher:
    """Отправка в фоне, сразу после коммита уведомления.

    Задача не может пользоваться сессией запроса: к моменту её выполнения запрос
    уже закрыт. Берёт свою из sessionmaker.

    Сознательное упрощение (см. «Принятые риски» в спецификации): ретраев нет,
    статус доставки нигде не хранится, и откат транзакции после отправки оставит
    сообщение в телеграме.
    """

    def __init__(
        self,
        maker: async_sessionmaker[AsyncSession],
        registry: ChannelRegistry,
        settings: Settings,
    ) -> None:
        self._maker = maker
        self._registry = registry
        self._settings = settings
        # Ссылки на задачи, чтобы сборщик мусора не убрал их на полпути
        self._tasks: set[asyncio.Task[int]] = set()

    def schedule(self, notification_id: uuid.UUID) -> None:
        task = asyncio.create_task(self.deliver(notification_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def deliver(self, notification_id: uuid.UUID) -> int:
        """Разослать уведомление по включённым каналам; сколько каналов приняли."""
        async with self._maker() as session:
            notification = await NotificationRepository(session).get(notification_id)
            if notification is None:
                # Транзакция создателя откатилась — доставлять нечего
                return 0
            channels = await UserChannelRepository(session).list_enabled(notification.user_id)
            message = ChannelMessage(
                title=notification.title,
                body=notification.body,
                link=self._absolute(notification.link),
            )
            addresses = [(binding.channel, binding.address) for binding in channels]

        delivered = 0
        for kind, address in addresses:
            channel = self._registry.get(ChannelKind(kind))
            if channel is None:
                continue
            try:
                await channel.send(address, message)
            except Exception as error:
                logger.warning(
                    "Не доставлено уведомление %s в канал %s: %s", notification_id, kind, error
                )
                continue
            delivered += 1
        return delivered

    def _absolute(self, link: str | None) -> str | None:
        """Относительный путь из уведомления — в абсолютный URL для внешнего канала."""
        if not link:
            return None
        if link.startswith("http://") or link.startswith("https://"):
            return link
        return f"{self._settings.notify.public_url}/{link.lstrip('/')}"
```

- [ ] **Step 4: Подключить настоящий диспетчер к DI**

В `backend/app/domains/notification/provider.py` добавить провайдер каналов и заменить им `NullDispatcherProvider` в боевом контейнере:

```python
class ChannelsProvider(Provider):
    """Реестр каналов и доставка. Один на приложение."""

    scope = Scope.APP

    @provide
    def registry(self, settings: Settings) -> ChannelRegistry:
        return create_channel_registry(settings)

    @provide
    def dispatcher(
        self,
        maker: async_sessionmaker[AsyncSession],
        registry: ChannelRegistry,
        settings: Settings,
    ) -> NotificationDispatcher:
        return BackgroundDispatcher(maker=maker, registry=registry, settings=settings)
```

с импортами:

```python
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.notify.factory import ChannelRegistry, create_channel_registry
from app.core.settings import Settings
from app.domains.notification.dispatcher import BackgroundDispatcher
```

В `backend/app/plugins/di.py` заменить `NullDispatcherProvider()` на `ChannelsProvider()` и поправить импорт. В `backend/tests/conftest.py` оставить `NullDispatcherProvider()` — тесты не должны ничего отправлять.

- [ ] **Step 5: Запустить тесты и убедиться, что проходят**

Run: `cd backend && uv run pytest tests/test_notification_dispatcher.py -v`
Expected: PASS, 5 passed

- [ ] **Step 6: Прогнать весь бэкенд и закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make test && make pretty && make check
git add backend/app backend/tests
git commit -m "feat(backend): доставка уведомлений по каналам"
```

---

## Task 8: Привязка и отвязка каналов

**Files:**
- Create: `backend/app/domains/notification/channels.py`
- Modify: `backend/app/domains/notification/router.py`
- Modify: `backend/app/domains/notification/provider.py`
- Modify: `backend/app/plugins/routing.py`
- Test: `backend/tests/test_notification_channels_api.py`

**Interfaces:**
- Consumes: `UserChannelRepository`, `ChannelLinkTokenRepository` (Task 3), `NotifySettings` (Task 1)
- Produces:
  - `ChannelLinkService.issue(user_id, channel) -> ChannelLinkResponse`
  - `ChannelLinkService.redeem(token: str, address: str) -> UserChannel`
  - `ChannelLinkService.list_for(user_id) -> list[UserChannelRead]`
  - `ChannelLinkService.set_enabled(user_id, channel, enabled) -> UserChannelRead`
  - `ChannelLinkService.unlink(user_id, channel) -> None`
  - `mask_address(address: str) -> str`
  - `LINK_TOKEN_TTL_MINUTES = 15`
  - Роутер `channels_router` с префиксом `/users/me/channels`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_notification_channels_api.py`:

```python
"""Привязка каналов: выдача токена, погашение, тумблер, отвязка."""

from datetime import UTC, datetime, timedelta

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notification.channels import ChannelLinkService, mask_address
from app.domains.notification.models import ChannelKind, ChannelLinkToken, Notification
from app.domains.notification.repository import (
    ChannelLinkTokenRepository,
    UserChannelRepository,
)
from app.domains.notification.models import NotificationType
from app.core.settings import Settings
from app.domains.user.service import STAND_USER_ID, UserService
from app.plugins.exceptions import AppError


async def seed(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


def make_service(session: AsyncSession) -> ChannelLinkService:
    settings = Settings()
    settings.notify.telegram.token = "123:abc"
    settings.notify.telegram.bot_username = "lct7_bot"
    return ChannelLinkService(
        channels=UserChannelRepository(session),
        tokens=ChannelLinkTokenRepository(session),
        session=session,
        settings=settings,
    )


def test_mask_shows_only_the_tail() -> None:
    assert mask_address("123456789") == "…6789"
    assert mask_address("42") == "…42"


async def test_issue_returns_deep_link(container: AsyncContainer) -> None:
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        issued = await make_service(session).issue(STAND_USER_ID, ChannelKind.TELEGRAM)

    assert issued.url.startswith("https://t.me/lct7_bot?start=")
    assert issued.expires_at > datetime.now(UTC)


async def test_redeem_creates_binding(container: AsyncContainer) -> None:
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        service = make_service(session)
        issued = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        token = issued.url.rsplit("=", 1)[1]

        binding = await service.redeem(token, address="777")

        assert binding.address == "777"
        assert binding.enabled is True


async def test_second_redeem_of_the_same_token_fails(container: AsyncContainer) -> None:
    """Review Focus 2: повторный /start не создаёт вторую привязку."""
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        service = make_service(session)
        issued = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        token = issued.url.rsplit("=", 1)[1]
        await service.redeem(token, address="777")

        with pytest.raises(AppError):
            await service.redeem(token, address="888")

        bindings = await UserChannelRepository(session).list_for_user(STAND_USER_ID)
        assert len(bindings) == 1
        assert bindings[0].address == "777"


async def test_expired_token_is_rejected(container: AsyncContainer) -> None:
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(
            ChannelLinkToken(
                token="e" * 32,
                user_id=STAND_USER_ID,
                channel=ChannelKind.TELEGRAM,
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        await session.commit()

        with pytest.raises(AppError):
            await make_service(session).redeem("e" * 32, address="777")


async def test_unknown_token_is_rejected(container: AsyncContainer) -> None:
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        with pytest.raises(AppError):
            await make_service(session).redeem("z" * 32, address="777")


async def test_relink_replaces_the_address(container: AsyncContainer) -> None:
    """Перепривязка с другого аккаунта телеграма меняет адрес, а не плодит строки."""
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        service = make_service(session)
        first = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        await service.redeem(first.url.rsplit("=", 1)[1], address="111")
        second = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        await service.redeem(second.url.rsplit("=", 1)[1], address="222")

        bindings = await UserChannelRepository(session).list_for_user(STAND_USER_ID)
        assert len(bindings) == 1
        assert bindings[0].address == "222"


# ---------- HTTP ----------


async def test_channels_endpoint_is_empty_at_first(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed(container)

    response = await client.get("/users/me/channels")

    assert response.status_code == 200
    assert response.json() == []


async def test_link_without_bot_configured_returns_409(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """В тестовом окружении токена бота нет — нерабочую ссылку выдавать нельзя."""
    await seed(container)

    response = await client.post("/users/me/channels/telegram/link")

    assert response.status_code == 409
    assert "не настроен" in response.json()["detail"]


async def test_toggle_and_unlink(client: AsyncClient, container: AsyncContainer) -> None:
    await seed(container)
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        service = make_service(session)
        issued = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        await service.redeem(issued.url.rsplit("=", 1)[1], address="123456789")

    listed = await client.get("/users/me/channels")
    toggled = await client.patch("/users/me/channels/telegram", json={"enabled": False})
    unlinked = await client.delete("/users/me/channels/telegram")
    after = await client.get("/users/me/channels")

    assert listed.json()[0]["address_masked"] == "…6789"
    assert "123456789" not in listed.text
    assert toggled.json()["enabled"] is False
    assert unlinked.status_code == 204
    assert after.json() == []


async def test_unlink_keeps_notification_history(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Отвязка канала — не удаление ленты."""
    await seed(container)
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(
            Notification(
                user_id=STAND_USER_ID,
                type=NotificationType.SYSTEM,
                title="Было",
                body="Текст",
            )
        )
        await session.commit()
        service = make_service(session)
        issued = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        await service.redeem(issued.url.rsplit("=", 1)[1], address="123456789")

    await client.delete("/users/me/channels/telegram")
    feed = await client.get("/notifications")

    assert len(feed.json()["items"]) == 1


async def test_toggle_missing_channel_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed(container)

    response = await client.patch("/users/me/channels/telegram", json={"enabled": True})

    assert response.status_code == 404
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd backend && uv run pytest tests/test_notification_channels_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domains.notification.channels'`

- [ ] **Step 3: Реализовать сервис привязки**

Создать `backend/app/domains/notification/channels.py`:

```python
"""Привязка каналов доставки: одноразовые токены, тумблер, отвязка."""

import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.domains.notification.models import ChannelKind, ChannelLinkToken, UserChannel
from app.domains.notification.repository import (
    ChannelLinkTokenRepository,
    UserChannelRepository,
)
from app.domains.notification.schemas import ChannelLinkResponse, UserChannelRead
from app.plugins.exceptions import AppError

# Столько живёт ссылка привязки: хватает дойти до телеграма и нажать «Запустить»
LINK_TOKEN_TTL_MINUTES = 15
# Длина колонки token в channel_link_tokens
TOKEN_LENGTH = 32


def mask_address(address: str) -> str:
    """Показать только хвост адреса: chat_id наружу не отдаём."""
    return f"…{address[-4:]}"


class ChannelLinkService:
    def __init__(
        self,
        channels: UserChannelRepository,
        tokens: ChannelLinkTokenRepository,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        self._channels = channels
        self._tokens = tokens
        self._session = session
        self._settings = settings

    async def list_for(self, user_id: uuid.UUID) -> list[UserChannelRead]:
        bindings: Sequence[UserChannel] = await self._channels.list_for_user(user_id)
        return [
            UserChannelRead(
                channel=ChannelKind(binding.channel),
                address_masked=mask_address(binding.address),
                enabled=binding.enabled,
                linked_at=binding.linked_at,
            )
            for binding in bindings
        ]

    async def issue(self, user_id: uuid.UUID, channel: ChannelKind) -> ChannelLinkResponse:
        """Выдать одноразовую ссылку привязки."""
        if channel is ChannelKind.TELEGRAM and not self._settings.notify.telegram_configured:
            raise AppError("Канал «телеграм» не настроен на сервере", status_code=409)

        token = secrets.token_urlsafe(24)[:TOKEN_LENGTH]
        expires_at = datetime.now(UTC) + timedelta(minutes=LINK_TOKEN_TTL_MINUTES)
        await self._tokens.add(
            ChannelLinkToken(
                token=token, user_id=user_id, channel=channel.value, expires_at=expires_at
            )
        )
        await self._session.commit()

        bot = self._settings.notify.telegram.bot_username
        return ChannelLinkResponse(url=f"https://t.me/{bot}?start={token}", expires_at=expires_at)

    async def redeem(self, token: str, address: str) -> UserChannel:
        """Погасить токен и привязать адрес. Зовётся поллером бота."""
        stored = await self._tokens.get(token)
        if stored is None or stored.used_at is not None:
            raise AppError("Ссылка привязки недействительна", status_code=404)
        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            # SQLite возвращает naive datetime; в Postgres колонка timezone-aware
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            raise AppError("Ссылка привязки устарела", status_code=410)

        kind = ChannelKind(stored.channel)
        existing = await self._channels.get_for(stored.user_id, kind)
        if existing is None:
            existing = UserChannel(
                user_id=stored.user_id, channel=kind.value, address=address, enabled=True
            )
            await self._channels.add(existing)
        else:
            # Перепривязка с другого аккаунта меняет адрес, а не плодит строки
            existing.address = address
            existing.enabled = True

        stored.used_at = datetime.now(UTC)
        await self._session.commit()
        return existing

    async def set_enabled(
        self, user_id: uuid.UUID, channel: ChannelKind, enabled: bool
    ) -> UserChannelRead:
        binding = await self._require(user_id, channel)
        binding.enabled = enabled
        await self._session.commit()
        return UserChannelRead(
            channel=channel,
            address_masked=mask_address(binding.address),
            enabled=binding.enabled,
            linked_at=binding.linked_at,
        )

    async def unlink(self, user_id: uuid.UUID, channel: ChannelKind) -> None:
        """Отвязать канал. Историю уведомлений не трогаем."""
        binding = await self._require(user_id, channel)
        await self._channels.delete(binding)
        await self._session.commit()

    async def _require(self, user_id: uuid.UUID, channel: ChannelKind) -> UserChannel:
        binding = await self._channels.get_for(user_id, channel)
        if binding is None:
            raise AppError("Канал не привязан", status_code=404)
        return binding
```

- [ ] **Step 4: Добавить роуты каналов**

Дописать в `backend/app/domains/notification/router.py`:

```python
channels_router = APIRouter(prefix="/users/me/channels", tags=["notifications"])


@channels_router.get("")
@inject
async def list_channels(
    user: FromDishka[CurrentUser],
    service: FromDishka[ChannelLinkService],
) -> list[UserChannelRead]:
    return await service.list_for(user.id)


@channels_router.post("/{channel}/link")
@inject
async def link_channel(
    channel: ChannelKind,
    user: FromDishka[CurrentUser],
    service: FromDishka[ChannelLinkService],
) -> ChannelLinkResponse:
    """Выдать одноразовую ссылку привязки канала."""
    return await service.issue(user.id, channel)


@channels_router.patch("/{channel}")
@inject
async def toggle_channel(
    channel: ChannelKind,
    data: ChannelToggle,
    user: FromDishka[CurrentUser],
    service: FromDishka[ChannelLinkService],
) -> UserChannelRead:
    return await service.set_enabled(user.id, channel, data.enabled)


@channels_router.delete("/{channel}", status_code=204)
@inject
async def unlink_channel(
    channel: ChannelKind,
    user: FromDishka[CurrentUser],
    service: FromDishka[ChannelLinkService],
) -> None:
    await service.unlink(user.id, channel)
```

с дополнением импортов в шапке файла:

```python
from app.domains.notification.channels import ChannelLinkService
from app.domains.notification.models import ChannelKind
from app.domains.notification.schemas import (
    ChannelLinkResponse,
    ChannelToggle,
    MarkReadResponse,
    NotificationList,
    NotificationRead,
    TestNotificationRequest,
    UserChannelRead,
)
```

- [ ] **Step 5: Подключить сервис и роутер**

В `NotificationProvider` (`provider.py`) добавить:

```python
    @provide(scope=Scope.REQUEST)
    def link_service(
        self,
        channels: UserChannelRepository,
        tokens: ChannelLinkTokenRepository,
        session: AsyncSession,
        settings: Settings,
    ) -> ChannelLinkService:
        return ChannelLinkService(channels, tokens, session, settings)
```

В `backend/app/plugins/routing.py` импортировать `channels_router` и добавить:

```python
api_router.include_router(channels_router, dependencies=[Depends(require_auth)])
```

- [ ] **Step 6: Запустить тесты и убедиться, что проходят**

Run: `cd backend && uv run pytest tests/test_notification_channels_api.py -v`
Expected: PASS, 13 passed

- [ ] **Step 7: Прогнать весь бэкенд и закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make test && make pretty && make check
git add backend/app backend/tests
git commit -m "feat(backend): привязка и отвязка каналов доставки"
```

---

## Task 9: Фоновая привязка телеграма

**Files:**
- Create: `backend/app/domains/notification/telegram_link.py`
- Modify: `backend/app/domains/notification/provider.py`
- Modify: `backend/app/plugins/di.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_telegram_link_poller.py`

**Interfaces:**
- Consumes: `ChannelLinkService` (Task 8), `TelegramClient` (Task 6), `async_sessionmaker`
- Produces:
  - `parse_start_token(text: str) -> str | None`
  - `TelegramLinkPoller(maker, client, settings)` с `async run_once() -> int`, `async start()`, `async stop()`
  - `async start_telegram_poller(container, settings) -> TelegramLinkPoller | None`

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_telegram_link_poller.py`:

```python
"""Поллер бота: разбор /start и привязка chat_id."""

from typing import Any

from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import Settings
from app.domains.notification.channels import ChannelLinkService
from app.domains.notification.models import ChannelKind
from app.domains.notification.repository import (
    ChannelLinkTokenRepository,
    UserChannelRepository,
)
from app.domains.notification.telegram_link import TelegramLinkPoller, parse_start_token
from app.domains.user.service import STAND_USER_ID, UserService


class FakeUpdatesClient:
    """Отдаёт заготовленные апдейты и запоминает ответы бота."""

    def __init__(self, updates: list[dict[str, Any]]) -> None:
        self._updates = updates
        self.sent: list[tuple[str, str]] = []

    async def get_updates(self, offset: int | None, timeout_s: int) -> list[dict[str, Any]]:
        batch = [u for u in self._updates if offset is None or u["update_id"] >= offset]
        return batch

    async def send_message(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))


def update(update_id: int, chat_id: int, text: str) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "message": {"chat": {"id": chat_id}, "text": text},
    }


def test_parse_start_token() -> None:
    assert parse_start_token("/start abc123") == "abc123"
    assert parse_start_token("/start   abc123  ") == "abc123"
    assert parse_start_token("/start@lct7_bot abc123") == "abc123"
    assert parse_start_token("/start") is None
    assert parse_start_token("привет") is None
    assert parse_start_token("") is None


def settings_with_bot() -> Settings:
    settings = Settings()
    settings.notify.telegram.token = "123:abc"
    settings.notify.telegram.bot_username = "lct7_bot"
    return settings


async def issue_token(container: AsyncContainer) -> str:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()
        session = await request_container.get(AsyncSession)
        link = ChannelLinkService(
            channels=UserChannelRepository(session),
            tokens=ChannelLinkTokenRepository(session),
            session=session,
            settings=settings_with_bot(),
        )
        issued = await link.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        return issued.url.rsplit("=", 1)[1]


async def test_start_with_token_binds_the_chat(container: AsyncContainer) -> None:
    token = await issue_token(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    client = FakeUpdatesClient([update(1, 424242, f"/start {token}")])
    poller = TelegramLinkPoller(maker, client, settings_with_bot())  # type: ignore[arg-type]

    handled = await poller.run_once()

    assert handled == 1
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        binding = await UserChannelRepository(session).get_for(
            STAND_USER_ID, ChannelKind.TELEGRAM
        )
        assert binding is not None
        assert binding.address == "424242"
    assert "привязаны" in client.sent[0][1]


async def test_second_start_with_same_token_reports_stale_link(
    container: AsyncContainer,
) -> None:
    """Review Focus 2: токен одноразовый, второй раз — понятный ответ, не падение."""
    token = await issue_token(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    client = FakeUpdatesClient(
        [update(1, 424242, f"/start {token}"), update(2, 999, f"/start {token}")]
    )
    poller = TelegramLinkPoller(maker, client, settings_with_bot())  # type: ignore[arg-type]

    await poller.run_once()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        bindings = await UserChannelRepository(session).list_for_user(STAND_USER_ID)
        assert len(bindings) == 1
        assert bindings[0].address == "424242"
    assert "недействительна" in client.sent[1][1] or "устарела" in client.sent[1][1]


async def test_plain_message_is_ignored_with_a_hint(container: AsyncContainer) -> None:
    await issue_token(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    client = FakeUpdatesClient([update(1, 424242, "привет")])
    poller = TelegramLinkPoller(maker, client, settings_with_bot())  # type: ignore[arg-type]

    handled = await poller.run_once()

    assert handled == 0
    assert len(client.sent) == 1


async def test_offset_advances_past_handled_updates(container: AsyncContainer) -> None:
    """Второй проход не должен повторно обрабатывать те же апдейты."""
    token = await issue_token(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    client = FakeUpdatesClient([update(7, 424242, f"/start {token}")])
    poller = TelegramLinkPoller(maker, client, settings_with_bot())  # type: ignore[arg-type]

    await poller.run_once()
    second = await poller.run_once()

    assert second == 0
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd backend && uv run pytest tests/test_telegram_link_poller.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domains.notification.telegram_link'`

- [ ] **Step 3: Реализовать поллер**

Создать `backend/app/domains/notification/telegram_link.py`:

```python
"""Фоновая привязка телеграма: long polling бота и разбор /start <токен>.

Устроено как app/domains/camera/stream.py: start()/stop(), запуск в lifespan
только при настроенном боте. Webhook не используется — ему нужен публичный HTTPS,
которого нет при локальной разработке.
"""

import asyncio
import logging
import re
from typing import Any

from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.notify.telegram import TelegramClient
from app.core.settings import Settings
from app.domains.notification.channels import ChannelLinkService
from app.domains.notification.repository import (
    ChannelLinkTokenRepository,
    UserChannelRepository,
)
from app.plugins.exceptions import AppError

logger = logging.getLogger(__name__)

# /start <токен>, в группах телеграм добавляет к команде имя бота
_START = re.compile(r"^/start(?:@\S+)?\s+(\S+)\s*$")

HELLO = (
    "Это бот уведомлений «Веха». Чтобы получать сюда уведомления, "
    "нажмите «Привязать» в личном кабинете на сайте."
)
LINKED = "Готово, уведомления привязаны к этому чату."


def parse_start_token(text: str) -> str | None:
    """Достать токен из текста команды; None — это не /start с токеном."""
    match = _START.match(text.strip())
    return match.group(1) if match else None


class TelegramLinkPoller:
    """Опрашивает Bot API и привязывает чаты по одноразовым токенам."""

    def __init__(
        self,
        maker: async_sessionmaker[AsyncSession],
        client: TelegramClient,
        settings: Settings,
    ) -> None:
        self._maker = maker
        self._client = client
        self._settings = settings
        # Курсор апдейтов живёт в памяти: телеграм хранит их сутки, после рестарта
        # поллер перечитает, а повторный /start по погашенному токену безвреден
        self._offset: int | None = None
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def run_once(self) -> int:
        """Разобрать одну пачку апдейтов; сколько чатов привязали."""
        updates = await self._client.get_updates(
            offset=self._offset, timeout_s=self._settings.notify.telegram.poll_timeout_s
        )
        linked = 0
        for update in updates:
            self._offset = int(update["update_id"]) + 1
            if await self._handle(update):
                linked += 1
        return linked

    async def _handle(self, update: dict[str, Any]) -> bool:
        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        text = message.get("text") or ""
        if chat_id is None:
            return False

        token = parse_start_token(text)
        if token is None:
            await self._reply(str(chat_id), HELLO)
            return False

        async with self._maker() as session:
            service = ChannelLinkService(
                channels=UserChannelRepository(session),
                tokens=ChannelLinkTokenRepository(session),
                session=session,
                settings=self._settings,
            )
            try:
                await service.redeem(token, address=str(chat_id))
            except AppError as error:
                await self._reply(str(chat_id), error.message)
                return False

        await self._reply(str(chat_id), LINKED)
        return True

    async def _reply(self, chat_id: str, text: str) -> None:
        try:
            await self._client.send_message(chat_id, text)
        except Exception as error:
            logger.warning("Не удалось ответить в чат %s: %s", chat_id, error)

    async def start(self) -> None:
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning("Поллер телеграма: %s", error)
                # Телеграм недоступен — не молотим его в холостую
                await asyncio.sleep(5)

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


async def start_telegram_poller(
    container: AsyncContainer, settings: Settings
) -> TelegramLinkPoller | None:
    """Запустить поллер, если бот настроен; иначе None и ничего не запущено."""
    if not settings.notify.telegram_configured:
        return None
    poller = await container.get(TelegramLinkPoller)
    await poller.start()
    return poller
```

- [ ] **Step 4: Подключить поллер к DI и lifespan**

В `backend/app/domains/notification/provider.py` добавить:

```python
class TelegramPollerProvider(Provider):
    """Поллер бота. Создаётся, только если бот настроен (см. main.py)."""

    scope = Scope.APP

    @provide
    def client(self, settings: Settings) -> TelegramClient:
        return TelegramClient(
            token=settings.notify.telegram.token or "",
            timeout_s=settings.notify.telegram.request_timeout_s,
        )

    @provide
    def poller(
        self,
        maker: async_sessionmaker[AsyncSession],
        client: TelegramClient,
        settings: Settings,
    ) -> TelegramLinkPoller:
        return TelegramLinkPoller(maker, client, settings)
```

с импортами `TelegramClient` и `TelegramLinkPoller`. Добавить `TelegramPollerProvider()` в `create_container()` в `backend/app/plugins/di.py`.

В `backend/app/main.py` рядом с запуском `start_stream_capture`:

```python
    # Привязка телеграма — только при настроенном боте (NOTIFY__TELEGRAM__*)
    telegram_poller = await start_telegram_poller(app.state.dishka_container, settings)
```

и в блоке остановки после `yield`:

```python
    if telegram_poller is not None:
        await telegram_poller.stop()
```

плюс импорт `from app.domains.notification.telegram_link import start_telegram_poller`.

- [ ] **Step 5: Запустить тесты и убедиться, что проходят**

Run: `cd backend && uv run pytest tests/test_telegram_link_poller.py -v`
Expected: PASS, 5 passed

- [ ] **Step 6: Проверить, что без токена приложение стартует как раньше**

Run: `cd backend && uv run pytest -v`
Expected: PASS, все тесты бэкенда зелёные

- [ ] **Step 7: Закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make pretty && make check
git add backend/app backend/tests
git commit -m "feat(backend): фоновая привязка телеграма по одноразовому токену"
```

---

## Task 10: Примитив Drawer и иконка колокольчика

**Files:**
- Create: `frontend/src/components/ui/useDismissable.ts`
- Create: `frontend/src/components/ui/Drawer.tsx`
- Create: `frontend/src/components/ui/Drawer.module.css`
- Create: `frontend/src/components/ui/Drawer.test.tsx`
- Modify: `frontend/src/components/ui/Dialog.tsx`
- Modify: `frontend/src/components/ui/Icon.tsx`

**Interfaces:**
- Consumes: ничего
- Produces:
  - `useDismissable(onClose: () => void, ref: RefObject<HTMLElement | null>): void`
  - `Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode })`
  - иконка `bell` в `IconName`

- [ ] **Step 1: Написать падающий тест**

Создать `frontend/src/components/ui/Drawer.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Drawer } from './Drawer'

describe('Drawer', () => {
  it('показывает заголовок и содержимое', () => {
    render(
      <Drawer title="Уведомления" onClose={vi.fn()}>
        <p>Пусто</p>
      </Drawer>,
    )

    expect(screen.getByRole('dialog', { name: 'Уведомления' })).toBeInTheDocument()
    expect(screen.getByText('Пусто')).toBeInTheDocument()
  })

  it('закрывается по Escape', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Drawer title="Уведомления" onClose={onClose}>
        <p>Пусто</p>
      </Drawer>,
    )

    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('закрывается по клику на фон', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Drawer title="Уведомления" onClose={onClose}>
        <p>Пусто</p>
      </Drawer>,
    )

    await user.click(screen.getByRole('presentation'))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('не закрывается по клику внутри панели', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Drawer title="Уведомления" onClose={onClose}>
        <p>Пусто</p>
      </Drawer>,
    )

    await user.click(screen.getByText('Пусто'))

    expect(onClose).not.toHaveBeenCalled()
  })

  it('закрывается кнопкой', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Drawer title="Уведомления" onClose={onClose}>
        <p>Пусто</p>
      </Drawer>,
    )

    await user.click(screen.getByRole('button', { name: 'Закрыть' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd frontend && pnpm vitest run src/components/ui/Drawer.test.tsx`
Expected: FAIL — `Failed to resolve import "./Drawer"`

- [ ] **Step 3: Вынести общий хук**

Создать `frontend/src/components/ui/useDismissable.ts`:

```ts
import { useEffect, type RefObject } from 'react'

/**
 * Поведение всплывающей поверхности: Escape закрывает, фокус уходит внутрь и
 * возвращается на прежний элемент при размонтировании. Общее для Dialog и Drawer.
 */
export function useDismissable(onClose: () => void, ref: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    ref.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previous?.focus()
    }
  }, [onClose, ref])
}
```

Заменить в `frontend/src/components/ui/Dialog.tsx` блок `useEffect` на `useDismissable(onClose, ref)`, убрав теперь лишний импорт `useEffect`.

- [ ] **Step 4: Реализовать Drawer**

Создать `frontend/src/components/ui/Drawer.tsx`:

```tsx
import { useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Button } from './Button'
import { useDismissable } from './useDismissable'
import styles from './Drawer.module.css'

interface DrawerProps {
  title: string
  onClose: () => void
  children: ReactNode
}

/** Шторка справа на всю высоту: закрывается по Escape и клику по фону. */
export function Drawer({ title, onClose, children }: DrawerProps) {
  const titleId = useId()
  const ref = useRef<HTMLDivElement>(null)
  useDismissable(onClose, ref)

  return createPortal(
    <div
      className={styles.scrim}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={styles.sheet}
      >
        <div className={styles.head}>
          <h2 id={titleId}>{title}</h2>
          <Button variant="ghost" size="icon" icon="close" aria-label="Закрыть" onClick={onClose} />
        </div>
        <div className={styles.body}>{children}</div>
      </div>
    </div>,
    document.body,
  )
}
```

Создать `frontend/src/components/ui/Drawer.module.css`:

```css
.scrim {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  justify-content: flex-end;
  background: var(--scrim);
}

.sheet {
  display: flex;
  flex-direction: column;
  width: min(420px, 100%);
  height: 100%;
  padding: var(--space-6);
  gap: var(--space-4);
  background: var(--surface);
  box-shadow: var(--shadow-pop);
}

.head {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
}

.head h2 {
  flex-grow: 1;
}

.body {
  flex-grow: 1;
  overflow-y: auto;
}
```

- [ ] **Step 5: Добавить иконку колокольчика**

В `frontend/src/components/ui/Icon.tsx` добавить в объект `ICONS`:

```tsx
  bell: (
    <>
      <path d="M18 15V10a6 6 0 10-12 0v5l-2 3h16l-2-3z" />
      <path d="M10 21h4" />
    </>
  ),
```

- [ ] **Step 6: Запустить тесты и убедиться, что проходят**

Run: `cd frontend && pnpm vitest run src/components/ui`
Expected: PASS — тесты `Drawer` и существующие тесты `Dialog` зелёные

- [ ] **Step 7: Закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make front-pretty
git add frontend/src/components/ui
git commit -m "feat(frontend): примитив Drawer и иконка колокольчика"
```

---

## Task 11: Схемы, ключи и слой API

**Files:**
- Modify: `frontend/src/api/schemas.ts`
- Modify: `frontend/src/api/keys.ts`
- Create: `frontend/src/api/notifications.ts`
- Create: `frontend/src/api/notifications.test.tsx`

**Interfaces:**
- Consumes: `request` из `api/client.ts`
- Produces:
  - схемы `notificationSchema`, `notificationListSchema`, `channelKindSchema`, `userChannelSchema`, `channelLinkSchema`; типы `Notification`, `NotificationList`, `UserChannel`, `ChannelKind`
  - ключи `keys.notifications`, `keys.channels`
  - `notificationsApi` с `list`, `markAllRead`, `createTest`, `listChannels`, `link`, `toggle`, `unlink`
  - хуки `useNotifications`, `useMarkAllRead`, `useCreateTestNotification`, `useChannels`, `useLinkChannel`, `useToggleChannel`, `useUnlinkChannel`

- [ ] **Step 1: Написать падающий тест**

Создать `frontend/src/api/notifications.test.tsx`:

```tsx
import { describe, expect, it } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { createTestQueryClient } from '@/test/render'
import {
  useChannels,
  useCreateTestNotification,
  useMarkAllRead,
  useNotifications,
} from './notifications'

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
}

describe('api уведомлений', () => {
  it('лента приходит пустой и валидируется схемой', async () => {
    const { result } = renderHook(() => useNotifications(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual({ items: [], unread_count: 0 })
  })

  it('созданное уведомление попадает в ленту', async () => {
    const { result: create } = renderHook(() => useCreateTestNotification(), { wrapper })
    create.current.mutate({})
    await waitFor(() => expect(create.current.isSuccess).toBe(true))

    const { result: feed } = renderHook(() => useNotifications(), { wrapper })
    await waitFor(() => expect(feed.current.data?.unread_count).toBe(1))
  })

  it('пометка прочитанным обнуляет счётчик', async () => {
    const { result: create } = renderHook(() => useCreateTestNotification(), { wrapper })
    create.current.mutate({})
    await waitFor(() => expect(create.current.isSuccess).toBe(true))

    const { result: read } = renderHook(() => useMarkAllRead(), { wrapper })
    read.current.mutate()
    await waitFor(() => expect(read.current.isSuccess).toBe(true))

    const { result: feed } = renderHook(() => useNotifications(), { wrapper })
    await waitFor(() => expect(feed.current.data?.unread_count).toBe(0))
  })

  it('список каналов приходит пустым', async () => {
    const { result } = renderHook(() => useChannels(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([])
  })
})
```

Тест опирается на MSW-хендлеры из Task 12 — порядок задач здесь обратный привычному, поэтому сначала запускаем, видим падение на `onUnhandledRequest: 'error'`, и этот красный остаётся до Task 12.

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd frontend && pnpm vitest run src/api/notifications.test.tsx`
Expected: FAIL — `Failed to resolve import "./notifications"`

- [ ] **Step 3: Добавить zod-схемы**

Дописать в `frontend/src/api/schemas.ts`:

```ts
/** Уведомление. Тип — свободная строка: бэкенд пополняет список без миграций. */
export const notificationSchema = z.object({
  id: z.string(),
  type: z.string(),
  title: z.string(),
  body: z.string(),
  link: z.string().nullable(),
  read_at: z.string().nullable(),
  created_at: z.string(),
})
export type Notification = z.infer<typeof notificationSchema>

export const notificationListSchema = z.object({
  items: z.array(notificationSchema),
  unread_count: z.number(),
})
export type NotificationList = z.infer<typeof notificationListSchema>

export const markReadSchema = z.object({ marked: z.number() })

export const channelKindSchema = z.enum(['telegram'])
export type ChannelKind = z.infer<typeof channelKindSchema>

/** Привязка канала. Полного адреса фронт не видит. */
export const userChannelSchema = z.object({
  channel: channelKindSchema,
  address_masked: z.string(),
  enabled: z.boolean(),
  linked_at: z.string(),
})
export type UserChannel = z.infer<typeof userChannelSchema>

export const channelLinkSchema = z.object({
  url: z.string(),
  expires_at: z.string(),
})
export type ChannelLink = z.infer<typeof channelLinkSchema>
```

- [ ] **Step 4: Добавить ключи и слой API**

В `frontend/src/api/keys.ts` добавить в объект `keys`:

```ts
  notifications: ['notifications'] as const,
  channels: ['me', 'channels'] as const,
```

Создать `frontend/src/api/notifications.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { request } from './client'
import { keys } from './keys'
import { z } from 'zod'
import {
  channelLinkSchema,
  markReadSchema,
  notificationListSchema,
  notificationSchema,
  userChannelSchema,
  type ChannelKind,
} from './schemas'

interface TestNotification {
  title?: string
  body?: string
  link?: string | null
}

export const notificationsApi = {
  list: () => request('/notifications', { schema: notificationListSchema }),
  markAllRead: () =>
    request('/notifications/read', { method: 'POST', schema: markReadSchema }),
  createTest: (body: TestNotification) =>
    request('/notifications/test', { method: 'POST', body, schema: notificationSchema }),
  listChannels: () =>
    request('/users/me/channels', { schema: z.array(userChannelSchema) }),
  link: (channel: ChannelKind) =>
    request(`/users/me/channels/${channel}/link`, {
      method: 'POST',
      schema: channelLinkSchema,
    }),
  toggle: (channel: ChannelKind, enabled: boolean) =>
    request(`/users/me/channels/${channel}`, {
      method: 'PATCH',
      body: { enabled },
      schema: userChannelSchema,
    }),
  unlink: (channel: ChannelKind) =>
    request(`/users/me/channels/${channel}`, { method: 'DELETE' }),
}

/** Лента и счётчик непрочитанных. Опрос раз в полминуты — вебсокетов в проекте нет. */
export function useNotifications() {
  return useQuery({
    queryKey: keys.notifications,
    queryFn: notificationsApi.list,
    refetchInterval: 30_000,
  })
}

export function useMarkAllRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.notifications }),
  })
}

export function useCreateTestNotification() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: TestNotification) => notificationsApi.createTest(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.notifications }),
  })
}

export function useChannels() {
  return useQuery({ queryKey: keys.channels, queryFn: notificationsApi.listChannels })
}

export function useLinkChannel() {
  return useMutation({ mutationFn: (channel: ChannelKind) => notificationsApi.link(channel) })
}

export function useToggleChannel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ channel, enabled }: { channel: ChannelKind; enabled: boolean }) =>
      notificationsApi.toggle(channel, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.channels }),
  })
}

export function useUnlinkChannel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (channel: ChannelKind) => notificationsApi.unlink(channel),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.channels }),
  })
}
```

- [ ] **Step 5: Проверить типы**

Run: `cd frontend && pnpm exec tsc --noEmit`
Expected: без ошибок

- [ ] **Step 6: Закоммитить**

Тест `notifications.test.tsx` остаётся красным до Task 12 — это ожидаемо и отмечено в самом файле.

```bash
cd /Users/fadegor05/codes/LCT-7 && make front-pretty
git add frontend/src/api
git commit -m "feat(frontend): схемы и слой API уведомлений"
```

---

## Task 12: Моки MSW

**Files:**
- Modify: `frontend/src/mocks/db.ts`
- Modify: `frontend/src/mocks/handlers.ts`

**Interfaces:**
- Consumes: типы `Notification`, `UserChannel` (Task 11)
- Produces: в `db` — `listNotifications()`, `createTestNotification(body)`, `markAllRead()`, `listChannels()`, `linkChannel(channel)`, `confirmLink(channel)`, `toggleChannel(channel, enabled)`, `unlinkChannel(channel)`; семь хендлеров

- [ ] **Step 1: Написать падающий тест**

Тест уже написан в Task 11 (`frontend/src/api/notifications.test.tsx`) и сейчас падает на отсутствующих хендлерах.

Run: `cd frontend && pnpm vitest run src/api/notifications.test.tsx`
Expected: FAIL — `Error: intercepted a request without a matching request handler`

- [ ] **Step 2: Добавить состояние в db.ts**

В `frontend/src/mocks/db.ts` добавить в импорт типов `Notification` и `UserChannel`, в тип состояния — два поля, в `resetDb()` — их инициализацию (`notifications: []`, `channels: []`), и функции:

```ts
// ---------- Уведомления ----------

export function listNotifications(): { items: Notification[]; unread_count: number } {
  const items = [...state.notifications].reverse()
  return { items, unread_count: items.filter((n) => n.read_at === null).length }
}

export function createTestNotification(body: {
  title?: string
  body?: string
  link?: string | null
}): Notification {
  const created: Notification = {
    id: `notification-${++state.seq}`,
    type: 'system',
    title: body.title ?? 'Тестовое уведомление',
    body: body.body ?? 'Проверка системы уведомлений',
    link: body.link ?? null,
    read_at: null,
    created_at: new Date().toISOString(),
  }
  state.notifications.push(created)
  return created
}

export function markAllRead(): { marked: number } {
  const now = new Date().toISOString()
  let marked = 0
  for (const notification of state.notifications) {
    if (notification.read_at === null) {
      notification.read_at = now
      marked += 1
    }
  }
  return { marked }
}

// ---------- Каналы ----------

export function listChannels(): UserChannel[] {
  return state.channels.map((channel) => ({ ...channel }))
}

/**
 * В моках нет настоящего бота, поэтому ссылка привязки ведёт в никуда, а саму
 * привязку сразу подтверждает confirmLink — экран ведёт себя как после /start.
 */
export function linkChannel(channel: 'telegram'): { url: string; expires_at: string } {
  confirmLink(channel)
  return {
    url: `https://t.me/lct7_mock_bot?start=mock-${++state.seq}`,
    expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
  }
}

export function confirmLink(channel: 'telegram'): UserChannel {
  const existing = state.channels.find((c) => c.channel === channel)
  if (existing) {
    existing.enabled = true
    return existing
  }
  const created: UserChannel = {
    channel,
    address_masked: '…6789',
    enabled: true,
    linked_at: new Date().toISOString(),
  }
  state.channels.push(created)
  return created
}

export function toggleChannel(channel: 'telegram', enabled: boolean): UserChannel {
  const existing = state.channels.find((c) => c.channel === channel)
  if (!existing) throw new MockError(404, 'Канал не привязан')
  existing.enabled = enabled
  return existing
}

export function unlinkChannel(channel: 'telegram'): void {
  const index = state.channels.findIndex((c) => c.channel === channel)
  if (index < 0) throw new MockError(404, 'Канал не привязан')
  state.channels.splice(index, 1)
}
```

- [ ] **Step 3: Добавить хендлеры**

В `frontend/src/mocks/handlers.ts` добавить в массив `handlers`:

```ts
  // ---------- Уведомления ----------
  http.get(api('/notifications'), () => handle(db.listNotifications)),
  http.post(api('/notifications/read'), () => handle(db.markAllRead)),
  http.post(api('/notifications/test'), async ({ request }) => {
    const data = await json<{ title?: string; body?: string; link?: string | null }>(request)
    return handle(() => db.createTestNotification(data), 201)
  }),

  // ---------- Каналы доставки ----------
  http.get(api('/users/me/channels'), () => handle(db.listChannels)),
  http.post<{ channel: 'telegram' }>(api('/users/me/channels/:channel/link'), ({ params }) =>
    handle(() => db.linkChannel(params.channel)),
  ),
  http.patch<{ channel: 'telegram' }>(api('/users/me/channels/:channel'), async ({ params, request }) => {
    const data = await json<{ enabled: boolean }>(request)
    return handle(() => db.toggleChannel(params.channel, data.enabled))
  }),
  http.delete<{ channel: 'telegram' }>(api('/users/me/channels/:channel'), ({ params }) =>
    handle(() => {
      db.unlinkChannel(params.channel)
      return undefined
    }),
  ),
```

- [ ] **Step 4: Запустить тесты и убедиться, что проходят**

Run: `cd frontend && pnpm vitest run src/api/notifications.test.tsx`
Expected: PASS, 4 passed

- [ ] **Step 5: Закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make front-pretty
git add frontend/src/mocks frontend/src/api
git commit -m "feat(frontend): моки уведомлений и каналов"
```

---

## Task 13: Шторка уведомлений

**Files:**
- Create: `frontend/src/features/notifications/NotificationItem.tsx` + `.module.css`
- Create: `frontend/src/features/notifications/NotificationDrawer.tsx` + `.module.css`
- Create: `frontend/src/features/notifications/NotificationBell.tsx` + `.module.css`
- Create: `frontend/src/features/notifications/NotificationBell.test.tsx`
- Modify: `frontend/src/components/layout/AppLayout.tsx`

**Interfaces:**
- Consumes: `Drawer` (Task 10), `useNotifications`, `useMarkAllRead` (Task 11)
- Produces: `NotificationBell()` — самодостаточный блок для шапки, владеет состоянием шторки

- [ ] **Step 1: Написать падающий тест**

Создать `frontend/src/features/notifications/NotificationBell.test.tsx`:

```tsx
import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '@/test/render'
import { createTestNotification } from '@/mocks/db'
import { NotificationBell } from './NotificationBell'

describe('NotificationBell', () => {
  it('без непрочитанных бейджа нет', async () => {
    renderWithProviders(<NotificationBell />)

    await waitFor(() => expect(screen.getByRole('button', { name: /Уведомления/ })).toBeEnabled())
    expect(screen.queryByTestId('unread-badge')).not.toBeInTheDocument()
  })

  it('показывает число непрочитанных', async () => {
    createTestNotification({ title: 'Первое' })
    createTestNotification({ title: 'Второе' })
    renderWithProviders(<NotificationBell />)

    await waitFor(() => expect(screen.getByTestId('unread-badge')).toHaveTextContent('2'))
  })

  it('открытие шторки гасит бейдж, но оставляет пометки «новое»', async () => {
    createTestNotification({ title: 'Отклонение на объекте' })
    const { user } = renderWithProviders(<NotificationBell />)
    await waitFor(() => expect(screen.getByTestId('unread-badge')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /Уведомления/ }))

    expect(await screen.findByText('Отклонение на объекте')).toBeInTheDocument()
    expect(screen.getByText('новое')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByTestId('unread-badge')).not.toBeInTheDocument())
  })

  it('после закрытия и повторного открытия пометок «новое» нет', async () => {
    createTestNotification({ title: 'Отклонение на объекте' })
    const { user } = renderWithProviders(<NotificationBell />)
    await waitFor(() => expect(screen.getByTestId('unread-badge')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /Уведомления/ }))
    await screen.findByText('новое')
    await user.click(screen.getByRole('button', { name: 'Закрыть' }))
    await user.click(screen.getByRole('button', { name: /Уведомления/ }))

    expect(await screen.findByText('Отклонение на объекте')).toBeInTheDocument()
    expect(screen.queryByText('новое')).not.toBeInTheDocument()
  })

  it('пустая лента: шторка показывает заглушку', async () => {
    /** Review Focus 5. */
    const { user } = renderWithProviders(<NotificationBell />)

    await user.click(screen.getByRole('button', { name: /Уведомления/ }))

    expect(await screen.findByText('Пока ничего не произошло')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd frontend && pnpm vitest run src/features/notifications`
Expected: FAIL — `Failed to resolve import "./NotificationBell"`

- [ ] **Step 3: Реализовать элемент ленты**

Создать `frontend/src/features/notifications/NotificationItem.tsx`:

```tsx
import { Link } from 'react-router'
import type { Notification } from '@/api/schemas'
import styles from './NotificationItem.module.css'

interface NotificationItemProps {
  notification: Notification
  isNew: boolean
  onNavigate: () => void
}

/** Дата в формате ленты: «18.10, 14:30». */
function formatMoment(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function NotificationItem({ notification, isNew, onNavigate }: NotificationItemProps) {
  const content = (
    <>
      <div className={styles.head}>
        <span className={styles.title}>{notification.title}</span>
        {isNew && <span className={styles.badge}>новое</span>}
      </div>
      <p className={styles.body}>{notification.body}</p>
      <time className={styles.time} dateTime={notification.created_at}>
        {formatMoment(notification.created_at)}
      </time>
    </>
  )

  if (notification.link) {
    return (
      <li className={styles.item}>
        <Link to={notification.link} className={styles.link} onClick={onNavigate}>
          {content}
        </Link>
      </li>
    )
  }
  return <li className={styles.item}>{content}</li>
}
```

Создать `frontend/src/features/notifications/NotificationItem.module.css`:

```css
.item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--line);
}

.link {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  color: inherit;
  text-decoration: none;
}

.head {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}

.title {
  flex-grow: 1;
  font-weight: 600;
}

.badge {
  padding: 0 var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: var(--on-accent);
  font-size: 0.75rem;
}

.body {
  margin: 0;
  color: var(--ink-muted);
}

.time {
  color: var(--ink-muted);
  font-size: 0.75rem;
}
```

- [ ] **Step 4: Реализовать шторку**

Создать `frontend/src/features/notifications/NotificationDrawer.tsx`:

```tsx
import { useEffect, useRef } from 'react'
import { Drawer } from '@/components/ui/Drawer'
import { QueryState } from '@/components/ui/QueryState'
import { useMarkAllRead, useNotifications } from '@/api/notifications'
import { NotificationItem } from './NotificationItem'
import styles from './NotificationDrawer.module.css'

interface NotificationDrawerProps {
  onClose: () => void
}

export function NotificationDrawer({ onClose }: NotificationDrawerProps) {
  const feed = useNotifications()
  const markAllRead = useMarkAllRead()
  // Снимок непрочитанных на момент открытия: пометки «новое» должны дожить
  // до закрытия шторки, хотя на сервере всё уже прочитано
  const snapshot = useRef<Set<string> | null>(null)
  const markMutate = markAllRead.mutate

  useEffect(() => {
    if (snapshot.current !== null || !feed.data) return
    const unread = feed.data.items.filter((item) => item.read_at === null).map((item) => item.id)
    snapshot.current = new Set(unread)
    if (unread.length > 0) markMutate()
  }, [feed.data, markMutate])

  return (
    <Drawer title="Уведомления" onClose={onClose}>
      <QueryState query={feed}>
        {(data) =>
          data.items.length === 0 ? (
            <p className={styles.empty}>Пока ничего не произошло</p>
          ) : (
            <ul className={styles.list}>
              {data.items.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  isNew={snapshot.current?.has(notification.id) ?? false}
                  onNavigate={onClose}
                />
              ))}
            </ul>
          )
        }
      </QueryState>
    </Drawer>
  )
}
```

Создать `frontend/src/features/notifications/NotificationDrawer.module.css`:

```css
.list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.empty {
  margin: 0;
  color: var(--ink-muted);
}
```

- [ ] **Step 5: Реализовать колокольчик**

Создать `frontend/src/features/notifications/NotificationBell.tsx`:

```tsx
import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useNotifications } from '@/api/notifications'
import { NotificationDrawer } from './NotificationDrawer'
import styles from './NotificationBell.module.css'

/** Колокольчик в шапке: бейдж непрочитанных и шторка с лентой. */
export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const feed = useNotifications()
  const unread = feed.data?.unread_count ?? 0

  return (
    <div className={styles.wrap}>
      <Button
        variant="ghost"
        size="icon"
        icon="bell"
        aria-label={unread > 0 ? `Уведомления, непрочитанных: ${unread}` : 'Уведомления'}
        onClick={() => setOpen(true)}
      />
      {unread > 0 && (
        <span className={styles.badge} data-testid="unread-badge">
          {unread}
        </span>
      )}
      {open && <NotificationDrawer onClose={() => setOpen(false)} />}
    </div>
  )
}
```

Создать `frontend/src/features/notifications/NotificationBell.module.css`:

```css
.wrap {
  position: relative;
  display: inline-flex;
}

.badge {
  position: absolute;
  top: -2px;
  right: -2px;
  min-width: 18px;
  padding: 0 4px;
  border-radius: 9px;
  background: var(--accent);
  color: var(--on-accent);
  font-size: 0.6875rem;
  line-height: 18px;
  text-align: center;
}
```

- [ ] **Step 6: Встроить в шапку**

В `frontend/src/components/layout/AppLayout.tsx` добавить импорт `NotificationBell` и поставить его в `div.userSection` перед именем пользователя:

```tsx
        <div className={styles.userSection}>
          <NotificationBell />
          {me.data && <span className={styles.userName}>{me.data.full_name}</span>}
```

- [ ] **Step 7: Запустить тесты и убедиться, что проходят**

Run: `cd frontend && pnpm vitest run src/features/notifications src/components/layout`
Expected: PASS — пять тестов колокольчика и существующие тесты раскладки зелёные

- [ ] **Step 8: Закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make front-pretty
git add frontend/src/features/notifications frontend/src/components/layout
git commit -m "feat(frontend): шторка уведомлений и бейдж в шапке"
```

---

## Task 14: Личный кабинет

**Files:**
- Create: `frontend/src/features/profile/ChannelList.tsx` + `.module.css`
- Create: `frontend/src/pages/ProfilePage.tsx` + `.module.css`
- Create: `frontend/src/pages/ProfilePage.test.tsx`
- Modify: `frontend/src/app/routes.tsx`
- Modify: `frontend/src/components/layout/AppLayout.tsx`

**Interfaces:**
- Consumes: `useChannels`, `useLinkChannel`, `useToggleChannel`, `useUnlinkChannel` (Task 11), `useMe` из `api/auth`
- Produces: страница по маршруту `/profile`; `ChannelList()`

- [ ] **Step 1: Написать падающий тест**

Создать `frontend/src/pages/ProfilePage.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderRoute } from '@/test/render'

describe('Личный кабинет', () => {
  it('показывает ФИО пользователя', async () => {
    renderRoute('/profile')

    expect(await screen.findByLabelText('ФИО')).toHaveValue('инженер [ФИО]')
  })

  it('канал не привязан — предлагает привязать', async () => {
    renderRoute('/profile')

    expect(await screen.findByText('Телеграм')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Привязать' })).toBeInTheDocument()
  })

  it('привязка открывает ссылку и показывает канал привязанным', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const { user } = renderRoute('/profile')
    await screen.findByRole('button', { name: 'Привязать' })

    await user.click(screen.getByRole('button', { name: 'Привязать' }))

    await waitFor(() => expect(open).toHaveBeenCalled())
    expect(await screen.findByText('…6789')).toBeInTheDocument()
    open.mockRestore()
  })

  it('тумблер выключает доставку', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const { user } = renderRoute('/profile')
    await user.click(await screen.findByRole('button', { name: 'Привязать' }))
    const toggle = await screen.findByRole('checkbox', { name: 'Слать сюда' })

    await user.click(toggle)

    await waitFor(() => expect(toggle).not.toBeChecked())
    open.mockRestore()
  })

  it('отвязка убирает канал', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const { user } = renderRoute('/profile')
    await user.click(await screen.findByRole('button', { name: 'Привязать' }))
    await screen.findByText('…6789')

    await user.click(screen.getByRole('button', { name: 'Отвязать' }))

    expect(await screen.findByRole('button', { name: 'Привязать' })).toBeInTheDocument()
    open.mockRestore()
  })
})
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `cd frontend && pnpm vitest run src/pages/ProfilePage.test.tsx`
Expected: FAIL — маршрута `/profile` нет, отрисовывается `NotFoundPage`

- [ ] **Step 3: Реализовать список каналов**

Создать `frontend/src/features/profile/ChannelList.tsx`:

```tsx
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { QueryState } from '@/components/ui/QueryState'
import {
  useChannels,
  useLinkChannel,
  useToggleChannel,
  useUnlinkChannel,
} from '@/api/notifications'
import styles from './ChannelList.module.css'

const CHANNEL_TITLES = { telegram: 'Телеграм' } as const

/** Привязка каналов доставки. Пока канал один — телеграм. */
export function ChannelList() {
  const channels = useChannels()
  const link = useLinkChannel()
  const toggle = useToggleChannel()
  const unlink = useUnlinkChannel()

  const handleLink = () => {
    link.mutate('telegram', {
      onSuccess: (data) => {
        // Пользователь уходит в телеграм и жмёт «Запустить»; привязку поймает
        // следующий опрос списка каналов
        window.open(data.url, '_blank', 'noopener')
        void channels.refetch()
      },
    })
  }

  return (
    <QueryState query={channels}>
      {(data) => {
        const telegram = data.find((channel) => channel.channel === 'telegram')
        return (
          <Card>
            <div className={styles.row}>
              <span className={styles.name}>{CHANNEL_TITLES.telegram}</span>
              {telegram ? (
                <>
                  <span className={styles.address}>{telegram.address_masked}</span>
                  <label className={styles.toggle}>
                    <input
                      type="checkbox"
                      checked={telegram.enabled}
                      onChange={(event) =>
                        toggle.mutate({ channel: 'telegram', enabled: event.target.checked })
                      }
                    />
                    Слать сюда
                  </label>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => unlink.mutate('telegram')}
                  >
                    Отвязать
                  </Button>
                </>
              ) : (
                <Button size="sm" onClick={handleLink} disabled={link.isPending}>
                  Привязать
                </Button>
              )}
            </div>
            {link.isError && <p className={styles.error}>{link.error.message}</p>}
          </Card>
        )
      }}
    </QueryState>
  )
}
```

Создать `frontend/src/features/profile/ChannelList.module.css`:

```css
.row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.name {
  font-weight: 600;
}

.address {
  color: var(--ink-muted);
}

.toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
}

.error {
  margin: var(--space-3) 0 0;
  color: var(--status-behind);
}
```

- [ ] **Step 4: Реализовать страницу**

Создать `frontend/src/pages/ProfilePage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { TextField } from '@/components/ui/TextField'
import { request } from '@/api/client'
import { keys } from '@/api/keys'
import { userSchema } from '@/api/schemas'
import { useMe } from '@/api/auth'
import { ChannelList } from '@/features/profile/ChannelList'
import styles from './ProfilePage.module.css'

export function ProfilePage() {
  const me = useMe()
  const qc = useQueryClient()
  const [fullName, setFullName] = useState('')

  useEffect(() => {
    if (me.data) setFullName(me.data.full_name)
  }, [me.data])

  const rename = useMutation({
    mutationFn: (value: string) =>
      request('/users/me', { method: 'PATCH', body: { full_name: value }, schema: userSchema }),
    onSuccess: (user) => qc.setQueryData(keys.me, user),
  })

  return (
    <div className={styles.page}>
      <PageHeader title="Личный кабинет" />
      <Card>
        <form
          className={styles.form}
          onSubmit={(event) => {
            event.preventDefault()
            rename.mutate(fullName)
          }}
        >
          <TextField
            label="ФИО"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
          />
          <Button type="submit" disabled={rename.isPending || fullName.trim().length === 0}>
            Сохранить
          </Button>
        </form>
      </Card>
      <h2 className={styles.subtitle}>Куда слать уведомления</h2>
      <ChannelList />
    </div>
  )
}
```

Создать `frontend/src/pages/ProfilePage.module.css`:

```css
.page {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.form {
  display: flex;
  align-items: flex-end;
  gap: var(--space-4);
}

.subtitle {
  margin: 0;
}
```

- [ ] **Step 5: Добавить маршрут и ссылку в шапке**

В `frontend/src/app/routes.tsx` добавить импорт `ProfilePage` и внутрь `RequireAuth` строку перед `{ path: '*', ... }`:

```tsx
      { path: 'profile', element: <ProfilePage /> },
```

В `frontend/src/components/layout/AppLayout.tsx` сделать имя пользователя ссылкой:

```tsx
          {me.data && (
            <Link to="/profile" className={styles.userName}>
              {me.data.full_name}
            </Link>
          )}
```

- [ ] **Step 6: Запустить тесты и убедиться, что проходят**

Run: `cd frontend && pnpm vitest run src/pages/ProfilePage.test.tsx src/components/layout`
Expected: PASS, 5 тестов кабинета и тесты раскладки зелёные

- [ ] **Step 7: Прогнать все проверки фронта**

Run: `cd /Users/fadegor05/codes/LCT-7 && make front-check`
Expected: типы, линтеры, формат и покрытие зелёные. Если покрытие просело ниже порогов, дописать тесты на непокрытые ветки, а не править пороги.

- [ ] **Step 8: Закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7 && make front-pretty
git add frontend/src
git commit -m "feat(frontend): личный кабинет с привязкой каналов"
```

---

## Task 15: Документация и ручная проверка

**Files:**
- Modify: `documentation/data-model.md`, `documentation/api.md`, `documentation/architecture.md`, `documentation/configuration.md`, `documentation/limitations.md`
- Modify: `deploy/README.md` (раздел про переменные окружения)

**Interfaces:**
- Consumes: всё реализованное
- Produces: описание подсистемы в `documentation/`

- [ ] **Step 1: Прогнать полный набор проверок**

```bash
cd /Users/fadegor05/codes/LCT-7
make test && make check && make front-check
```

Expected: всё зелёное. Красное чинить здесь, а не записывать в известные ограничения.

- [ ] **Step 2: Поднять стенд и проверить руками**

```bash
cd /Users/fadegor05/codes/LCT-7 && make dev
```

Проверить по шагам:

1. Открыть `http://localhost`, войти.
2. `curl -X POST http://localhost/api/notifications/test -H "Authorization: Bearer <токен>" -H 'Content-Type: application/json' -d '{}'` — в шапке появился бейдж `1`.
3. Открыть шторку: уведомление видно с пометкой «новое», бейдж погас.
4. Закрыть и открыть шторку: пометки «новое» больше нет.
5. Зайти в личный кабинет: без `NOTIFY__TELEGRAM__TOKEN` кнопка «Привязать» отвечает «Канал «телеграм» не настроен на сервере».
6. Если есть токен бота: задать `NOTIFY__TELEGRAM__TOKEN` и `NOTIFY__TELEGRAM__BOT_USERNAME` в `.env`, перезапустить, привязать канал через `t.me`, создать тестовое уведомление, убедиться, что сообщение пришло в чат.

- [ ] **Step 3: Описать подсистему в documentation/**

Дописать по файлам:

- `documentation/data-model.md` — три новые таблицы и назначение каждой колонки, с оговоркой, что `type` и `channel` это строки, а не постгресовые `ENUM`.
- `documentation/api.md` — семь эндпоинтов с кодами ответов, включая 409 «канал не настроен» и 410 «ссылка устарела».
- `documentation/architecture.md` — домен `notification`, адаптеры каналов и фоновый поллер телеграма; реализован только телеграм.
- `documentation/configuration.md` — `NOTIFY__TELEGRAM__TOKEN`, `NOTIFY__TELEGRAM__BOT_USERNAME`, `NOTIFY__PUBLIC_URL` и поведение без них.
- `documentation/limitations.md` — доставка без ретраев и статуса, источников событий пока нет, почты и СМС нет.

Писать только про то, что реализовано: `documentation/` описывает код, а не замысел.

- [ ] **Step 4: Дополнить deploy/README.md**

В разделе про `.env` на ВМ дописать строку про переменные `NOTIFY__*` и то, что без них уведомления остаются только в интерфейсе.

- [ ] **Step 5: Закоммитить**

```bash
cd /Users/fadegor05/codes/LCT-7
git add documentation deploy/README.md
git commit -m "docs: система уведомлений"
```

- [ ] **Step 6: Открыть pull request**

```bash
cd /Users/fadegor05/codes/LCT-7
git push -u origin feat/notifications
gh pr create --title "feat: система уведомлений" --body "$(cat <<'EOF'
## Что сделано

Лента уведомлений для пользователя: таблица в БД, шторка на сайте, доставка в телеграм через адаптеры каналов и управление привязкой в личном кабинете.

- Новый домен `notification`: три таблицы, семь эндпоинтов, внутренний шов `NotificationService.notify()` для доменов-источников.
- Тип уведомления — питоновский `StrEnum` поверх `String(64)`, без постгресового `ENUM`: новый тип не требует миграции.
- Адаптеры каналов по образцу `adapters/storage`; реально реализован телеграм, без токена канал деградирует в запись в лог.
- Привязка телеграма — одноразовый токен в БД плюс long polling бота в фоновой задаче.
- Фронт: примитив `Drawer`, шторка с бейджем непрочитанных, страница `/profile`.

## Что не входит

Источников событий нет — домены подключатся к `notify()` позже. Почта и СМС не реализованы. Доставка без outbox и ретраев, риск описан в спецификации.

## Проверка

`make test`, `make check`, `make front-check` — зелёные. Стенд проверен руками по сценарию из плана.

Спецификация: `docs/superpowers/specs/2026-10-18-notifications-design.md`
План: `docs/superpowers/plans/2026-10-18-notifications.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
