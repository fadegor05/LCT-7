# LCT-4 · User domain (stand mode, no auth) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the template `user` domain into the MVP stand domain: a single seeded `app_user` row, no
registration/login/passwords, and a `CurrentUser` DI dependency every other domain consumes.

**Architecture:** The MVP has no authentication (`docs/product.md` §14, §16). The `user` domain exists
only to own the single `app_user` row that signs records (`site.created_by`,
`hypothesis_decision.decided_by`) and to expose it as `CurrentUser` in `Scope.REQUEST`. `CurrentUser` is
the single seam that changes when real auth arrives: consumers never learn whether the identity came
from a seed row or from a token.

**Tech Stack:** Python 3.12+, FastAPI 0.141, Dishka 1.10, SQLAlchemy 2.0 (async), Alembic 1.20,
PostgreSQL (prod) / aiosqlite (tests), pytest 9 + pytest-asyncio + httpx, uv, ruff.

**Spec:** the "Specification" section of this document. The task decomposition below implements it.

## Global Constraints

- Source of truth for the data model: `docs/DataModel.md` §5.5 — `app_user` = "Один пользователь без
  авторизации, нужен для подписи решений («Решил: инженер [ФИО]»), seed одной строкой".
- No authentication, no authorization, no roles, no passwords, no tokens anywhere in the backend
  (`docs/product.md` §14, §16).
- Backend layout: `docs/architecture.md` §6.1–§6.4. One domain = one flat directory, only the six
  canonical files; `core/`, `plugins/`, `adapters/` are not domains.
- DI scopes: `Scope.APP` — settings, engine, sessionmaker. `Scope.REQUEST` — session, repositories,
  services, `CurrentUser`.
- Services own `AsyncSession` and call `commit()`; repositories only stage (`flush()`).
- ruff: line-length 100, target py312, lint select `E,F,I,UP,B`. `make check` must stay green after
  every task.
- **The tree must stay importable after every task.** `backend/tests/conftest.py` imports
  `app.main`, which transitively imports every domain module, so a task may not leave a dangling
  `from ... import Name`. The task order below is built around this.
- Comments and docstrings in Russian, matching the surrounding files. Commit messages in English.
- Every commit carries the trailer `Co-authored-by: Ivan Saydyashev <isarus2007@mail.ru>`.
- `backend/uv.lock` is gitignored — never stage it.

## Review Focus

Failure modes the spec implies that no happy-path test would catch. Each is assigned to the task that
owns the code.

1. **Double seeding.** `ensure_stand_user()` runs on every application start; the second run must not
   insert a second row, must not raise on the primary key, and must not reset an edited name.
   → Task 3: `test_ensure_stand_user_is_idempotent`, `test_ensure_stand_user_keeps_edited_name`.
2. **Un-seeded database.** Migrations ran but seeding did not (manual `alembic upgrade head`, a restored
   dump). `CurrentUser` must fail as a clear 503, not as an `AttributeError` on `None`.
   → Task 3: `test_current_user_missing_row_raises_503`; Task 4: `test_get_me_without_seed_returns_503`.
3. **Blank or oversized rename.** `PATCH /users/me` with `""`, `"   "` or 300 characters must be
   rejected with 422 — the name is printed verbatim in reports. → Task 4:
   `test_patch_me_rejects_blank_and_overlong_name`.
4. **Legacy fields leaking.** No response may carry `email`, `role`, or `hashed_password`; a stray
   schema field would resurrect a concept the MVP rejected. → Task 2:
   `test_no_auth_columns_remain`; Task 4: `test_me_response_has_no_legacy_fields`.
5. **In-memory SQLite losing the schema between connections.** Without `StaticPool` each async
   connection gets a fresh empty database and tests pass or fail on pool behaviour rather than on the
   code. → Task 1: `test_schema_survives_two_connections`.

---

## Specification

### Overview

`app/domains/user/` stops being an account-management domain and becomes the owner of the stand
identity:

- ORM class `User` → table **`app_user`** (`id`, `full_name`, `created_at`). The class keeps its plain
  name; the table is named `app_user` because `user` is reserved in PostgreSQL and because
  `DataModel.md` names it so.
- A fixed `STAND_USER_ID` constant plus an idempotent `ensure_stand_user()` seed run at startup.
- `CurrentUser` — a `NewType` over `User`, provided in `Scope.REQUEST`; the only symbol other domains
  import from this domain.
- Two endpoints: `GET /users/me` and `PATCH /users/me` (rename — with no registration, the report
  signature "Решил: инженер [ФИО]" has no other source).
- Deleted: `app/core/security.py`, the `bcrypt` dependency, `POST /users`, `GET /users`, and the
  `email` / `name` / `role` / `hashed_password` columns.

### Components

| File | Responsibility |
|---|---|
| `app/domains/user/models.py` | `User` ORM model, table `app_user` |
| `app/domains/user/schemas.py` | `UserRead`, `UserUpdate` |
| `app/domains/user/repository.py` | `UserRepository(BaseRepository[User])` |
| `app/domains/user/service.py` | `STAND_USER_ID`, `STAND_USER_DEFAULT_NAME`, `UserService` |
| `app/domains/user/provider.py` | `CurrentUser` NewType + `UserProvider` |
| `app/domains/user/router.py` | `GET /users/me`, `PATCH /users/me` |
| `app/main.py` | `create_app(container=None)`; lifespan seeds the stand user |
| `migrations/versions/0002_app_user.py` | drop `users`, create `app_user` |
| `tests/conftest.py` | aiosqlite container + app + httpx client fixtures |

### Interfaces / contracts

```python
# app/domains/user/models.py
class User(Base):
    __tablename__ = "app_user"
    id: Mapped[uuid.UUID]          # primary key, no default — the stand id is explicit
    full_name: Mapped[str]         # String(255)
    created_at: Mapped[datetime]   # DateTime(timezone=True), server_default=func.now()

# app/domains/user/service.py
STAND_USER_ID: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
STAND_USER_DEFAULT_NAME: str = "Инженер стройплощадки"

class UserService:
    def __init__(self, repository: UserRepository, session: AsyncSession) -> None: ...
    async def ensure_stand_user(self) -> User: ...   # idempotent get-or-create, commits
    async def get_current(self) -> User: ...         # raises AppError(503) when the row is absent
    async def rename(self, full_name: str) -> User: ...  # updates full_name, commits

# app/domains/user/provider.py
CurrentUser = NewType("CurrentUser", User)

class UserProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(UserRepository)
    service = provide(UserService)

    @provide
    async def current_user(self, service: UserService) -> CurrentUser: ...

# app/main.py
def create_app(container: AsyncContainer | None = None) -> FastAPI: ...
```

**HTTP contract** (mounted under `settings.api_prefix`, default `/api`):

| Method | Path | Request body | Responses |
|---|---|---|---|
| GET | `/api/users/me` | — | 200 `UserRead` · 503 when un-seeded |
| PATCH | `/api/users/me` | `UserUpdate` | 200 `UserRead` · 422 invalid name · 503 when un-seeded |

```python
class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    created_at: datetime

class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)  # so "   " fails min_length
    full_name: str = Field(min_length=1, max_length=255)
```

**Consumer contract for LCT-6 … LCT-11:**

```python
from dishka.integrations.fastapi import FromDishka, inject
from app.domains.user.provider import CurrentUser

@router.post("/sites")
@inject
async def create_site(user: FromDishka[CurrentUser], ...): ...
```

### Error handling

- Missing stand row → `AppError("Стенд не инициализирован: пользователь не создан", status_code=503)`,
  rendered by the existing handler in `app/plugins/exceptions.py` as `{"detail": ...}`.
- Invalid `full_name` → FastAPI/Pydantic 422, no custom handling.
- No other new error paths: there is nothing to authenticate and nothing to authorize.

### Testing approach

A new `backend/tests/` package — the backend has no tests today, and this plan creates the harness that
LCT-6 … LCT-11 will reuse.

- Engine: `sqlite+aiosqlite:///:memory:` with `poolclass=StaticPool` and
  `connect_args={"check_same_thread": False}`; otherwise every connection sees an empty database.
- Schema: `Base.metadata.create_all` in the fixture, not Alembic. The migration is verified separately
  by `uv run alembic upgrade --sql head`, which renders DDL without connecting to a database.
- The container is assembled in `conftest.py` from a settings provider, a SQLite database provider and
  the real `UserProvider`, then handed to `create_app(container=...)`. Production wiring is untouched.
- `httpx.ASGITransport` does not emit lifespan events, so tests seed explicitly via the container —
  which is exactly what makes the "un-seeded database" case testable.
- `asyncio_mode = "auto"`: test coroutines and async fixtures need no decorator.

### Definition of done (tied to LCT-4)

- [ ] Domain lives in `app/domains/user/`, its router is mounted, `/api/users/me` answers.
- [ ] `CurrentUser` resolves from the DI container for any other domain.
- [ ] Exactly one `app_user` row exists after startup, stable across restarts.
- [ ] No password, token, role, or email remains in the backend.
- [ ] `make check` green, `make test` green, `uv run alembic upgrade --sql head` renders.
- [ ] `docs/architecture.md` documents stand-mode identity and the `CurrentUser` seam.

**Deliberate deviation from the Linear ticket:** LCT-4 as written asks for registration, login, token
issuance and `PasswordHasher`/`TokenService` in `Scope.APP`. The human chose variant B (stand without
authentication) because the ticket contradicts `docs/product.md` §14/§16 and `docs/DataModel.md` §5.5.
Only the ticket's third DoD bullet ("`CurrentUser` available to other domains") survives verbatim. This
is recorded in the PR description and in a comment on LCT-4.

---

## Task 1: Test harness and injectable container

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/main.py`
- Modify: `makefile`
- Create: `backend/tests/__init__.py` (empty)
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_harness.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `create_app(container: AsyncContainer | None = None) -> FastAPI`; pytest fixtures
  `container` (`AsyncContainer` on in-memory SQLite), `app` (`FastAPI`), `client`
  (`httpx.AsyncClient`, `base_url="http://test/api"`). Tasks 3 and 4 build on these fixtures.

- [ ] **Step 1: Add dev dependencies and pytest configuration**

```bash
cd backend && uv add --dev pytest pytest-asyncio httpx aiosqlite
```

Then append to `backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

`pythonpath = ["."]` makes `import app` work when pytest runs from `backend/` (the project is not
installed: `[tool.uv] package = false`). Do not stage `backend/uv.lock` — it is gitignored.

- [ ] **Step 2: Write the failing harness test**

Create an empty `backend/tests/__init__.py`, and `backend/tests/test_harness.py`:

```python
"""Проверка тестового каркаса: приложение поднимается на in-memory SQLite."""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_health_answers(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_schema_survives_two_connections(engine: AsyncEngine) -> None:
    """StaticPool: второе соединение видит ту же базу, а не пустую."""
    async with engine.connect() as connection:
        first = await connection.scalar(
            text("SELECT count(*) FROM sqlite_master WHERE type = 'table'")
        )
    async with engine.connect() as connection:
        second = await connection.scalar(
            text("SELECT count(*) FROM sqlite_master WHERE type = 'table'")
        )

    assert first == second
    assert first > 0
```

- [ ] **Step 3: Run it to make sure it fails**

Run: `cd backend && uv run pytest tests/test_harness.py -v`
Expected: FAIL — fixtures `client` and `engine` not found.

- [ ] **Step 4: Make `create_app` accept a container**

In `backend/app/main.py` change only the signature and the wiring line:

```python
from dishka import AsyncContainer


def create_app(container: AsyncContainer | None = None) -> FastAPI:
    app = FastAPI(
        title="LCT-7 API",
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
    )

    setup_dishka(container or create_container(), app)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app
```

- [ ] **Step 5: Write `backend/tests/conftest.py`**

```python
"""Общие фикстуры бэкенда: контейнер на in-memory SQLite, приложение, HTTP-клиент.

Схема создаётся из метаданных (`create_all`), а не миграциями: миграции проверяются
отдельно (`alembic upgrade --sql head`), а тестам нужна только схема.
"""

from collections.abc import AsyncIterable, AsyncIterator

import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.settings import Settings, get_settings
from app.main import create_app
from app.models import Base


class TestAppProvider(Provider):
    scope = Scope.APP

    @provide
    def settings(self) -> Settings:
        return get_settings()


class TestDatabaseProvider(Provider):
    """Тот же контракт, что у DatabaseProvider, но поверх SQLite в памяти.

    StaticPool обязателен: без него каждое соединение получает свою пустую базу.
    """

    scope = Scope.APP

    @provide
    async def engine(self) -> AsyncIterable[AsyncEngine]:
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()

    @provide
    def sessionmaker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def session(self, maker: async_sessionmaker[AsyncSession]) -> AsyncIterable[AsyncSession]:
        async with maker() as session:
            yield session


@pytest.fixture
async def container() -> AsyncIterator[AsyncContainer]:
    container = make_async_container(TestAppProvider(), TestDatabaseProvider())
    yield container
    await container.close()


@pytest.fixture
async def engine(container: AsyncContainer) -> AsyncEngine:
    return await container.get(AsyncEngine)


@pytest.fixture
def app(container: AsyncContainer) -> FastAPI:
    return create_app(container)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api") as client:
        yield client
```

Note for the implementer: the container deliberately omits `UserProvider` at this stage — Task 3 adds
it together with the provider rewrite. `/health` needs no database.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest -v`
Expected: 2 passed.

- [ ] **Step 7: Add a `make test` target**

In the root `makefile`, right after the `check:` target:

```makefile
# Тесты бэкенда
test:
	cd backend && uv run pytest
```

and add `test` to the `.PHONY` line.

- [ ] **Step 8: Verify and commit**

```bash
make check && make test
git add backend/pyproject.toml backend/app/main.py backend/tests makefile
git commit -m "test(backend): add pytest harness with injectable DI container"
```

---

## Task 2: `app_user` model and migration

**Files:**
- Modify: `backend/app/domains/user/models.py`
- Modify: `backend/app/models.py` (comment only, if it mentions the old table)
- Create: `backend/migrations/versions/0002_app_user.py`
- Create: `backend/tests/test_user_model.py`

**Interfaces:**
- Consumes: the pytest harness from Task 1.
- Produces: `app.domains.user.models.User` with `__tablename__ = "app_user"` and exactly the columns
  `id: uuid.UUID`, `full_name: str`, `created_at: datetime`. Tasks 3 and 4 import it.

**Why the class keeps the name `User`:** `repository.py`, `service.py` and `router.py` still import
`User`/`UserRepository`/`UserService` at this point and are rewritten in Tasks 3–4. Renaming the class
here would break `import app.main` and take the whole test suite down with it. The columns that
disappear (`email`, `role`, `hashed_password`) are referenced only inside function bodies, so the tree
stays importable.

- [ ] **Step 1: Write the failing model test**

Create `backend/tests/test_user_model.py`:

```python
"""Модель соответствует docs/DataModel.md §5.5: таблица app_user, только id и ФИО."""

from app.domains.user.models import User


def test_table_is_app_user() -> None:
    assert User.__tablename__ == "app_user"


def test_columns_match_data_model() -> None:
    assert set(User.__table__.columns.keys()) == {"id", "full_name", "created_at"}


def test_no_auth_columns_remain() -> None:
    """Пароля, роли и email в MVP нет — см. product.md §14, §16."""
    assert set(User.__table__.columns.keys()).isdisjoint(
        {"email", "role", "hashed_password", "name"}
    )
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/test_user_model.py -v`
Expected: FAIL — `assert 'users' == 'app_user'`.

- [ ] **Step 3: Rewrite the model**

Replace the whole of `backend/app/domains/user/models.py`:

```python
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
```

- [ ] **Step 4: Run the model tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_user_model.py -v`
Expected: 3 passed.

- [ ] **Step 5: Write the migration**

Create `backend/migrations/versions/0002_app_user.py`:

```python
"""app_user: стендовый пользователь вместо шаблонной таблицы users

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-22

Таблица users пришла из шаблона (email/role/hashed_password) и в MVP не нужна:
авторизации нет (docs/product.md §14, §16). Данных в ней нет — переносить нечего,
она удаляется целиком.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.create_table(
        "app_user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("app_user")
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
```

- [ ] **Step 6: Verify the migration renders without a database**

Run: `cd backend && uv run alembic upgrade --sql head`
Expected: exit code 0, output contains `DROP TABLE users` and `CREATE TABLE app_user`.

- [ ] **Step 7: Run the whole suite and commit**

```bash
make check && make test
git add backend/app backend/migrations backend/tests
git commit -m "feat(backend): replace users table with single-row app_user"
```

---

## Task 3: Stand-user seeding, service and `CurrentUser`

**Files:**
- Modify: `backend/app/domains/user/repository.py`
- Modify: `backend/app/domains/user/service.py`
- Modify: `backend/app/domains/user/provider.py`
- Modify: `backend/app/domains/user/router.py` (only the two calls that would break — see Step 8)
- Modify: `backend/app/main.py`
- Modify: `backend/pyproject.toml` (drop `bcrypt`)
- Modify: `backend/tests/conftest.py` (register `UserProvider`)
- Delete: `backend/app/core/security.py`
- Create: `backend/tests/test_current_user.py`

**Interfaces:**
- Consumes: `User` (Task 2); fixtures `container` / `app` / `client` (Task 1).
- Produces: `STAND_USER_ID`, `STAND_USER_DEFAULT_NAME`, `UserService.ensure_stand_user()`,
  `UserService.get_current()`, `UserService.rename(full_name)`, and
  `app.domains.user.provider.CurrentUser`. Task 4 consumes all of them.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_current_user.py`:

```python
"""Стендовая идентичность: один seed-пользователь и контракт CurrentUser для других доменов."""

import pytest
from dishka import AsyncContainer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.user.models import User
from app.domains.user.provider import CurrentUser
from app.domains.user.service import STAND_USER_DEFAULT_NAME, STAND_USER_ID, UserService
from app.plugins.exceptions import AppError


async def test_ensure_stand_user_creates_row(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        user = await service.ensure_stand_user()

    assert user.id == STAND_USER_ID
    assert user.full_name == STAND_USER_DEFAULT_NAME


async def test_ensure_stand_user_is_idempotent(container: AsyncContainer) -> None:
    """Seed выполняется при каждом старте — второй прогон не должен дублировать строку."""
    for _ in range(2):
        async with container() as request_container:
            service = await request_container.get(UserService)
            await service.ensure_stand_user()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        total = await session.scalar(select(func.count()).select_from(User))

    assert total == 1


async def test_ensure_stand_user_keeps_edited_name(container: AsyncContainer) -> None:
    """Перезапуск приложения не откатывает ФИО, заданное инженером."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()
        await service.rename("Иванов И. И.")

    async with container() as request_container:
        service = await request_container.get(UserService)
        user = await service.ensure_stand_user()

    assert user.full_name == "Иванов И. И."


async def test_current_user_resolves_for_other_domains(container: AsyncContainer) -> None:
    """Контракт для доменов site/observation/...: личность берётся из DI, а не из домена user."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()

    async with container() as request_container:
        user = await request_container.get(CurrentUser)

    assert user.id == STAND_USER_ID


async def test_current_user_missing_row_raises_503(container: AsyncContainer) -> None:
    """База накатана миграциями, но не засеяна: понятная 503 вместо падения на None."""
    with pytest.raises(AppError) as exc_info:
        async with container() as request_container:
            await request_container.get(CurrentUser)

    assert exc_info.value.status_code == 503
```

- [ ] **Step 2: Register `UserProvider` in the test container**

In `backend/tests/conftest.py` add the import and extend the container:

```python
from app.domains.user.provider import UserProvider
```

```python
    container = make_async_container(TestAppProvider(), TestDatabaseProvider(), UserProvider())
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_current_user.py -v`
Expected: FAIL — `ImportError: cannot import name 'CurrentUser'`.

- [ ] **Step 4: Simplify the repository**

Replace `backend/app/domains/user/repository.py`:

```python
"""Доступ к данным стендового пользователя.

Своих запросов нет: таблица из одной строки, хватает get/add из BaseRepository.
"""

from app.core.repository import BaseRepository
from app.domains.user.models import User


class UserRepository(BaseRepository[User]):
    model = User
```

- [ ] **Step 5: Rewrite the service**

Replace `backend/app/domains/user/service.py`:

```python
"""Логика стендовой идентичности.

Авторизации в MVP нет (product.md §14): пользователь один, его идентификатор
зафиксирован константой, а строка создаётся при старте приложения.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.user.models import User
from app.domains.user.repository import UserRepository
from app.plugins.exceptions import AppError

# Идентификатор единственного пользователя стенда зашит константой, чтобы ссылки
# site.created_by и hypothesis_decision.decided_by переживали перезапуск сервиса.
STAND_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
STAND_USER_DEFAULT_NAME = "Инженер стройплощадки"


class UserService:
    def __init__(self, repository: UserRepository, session: AsyncSession) -> None:
        self._repository = repository
        self._session = session

    async def ensure_stand_user(self) -> User:
        """Идемпотентный seed: вызывается на каждом старте и не перетирает ФИО."""
        user = await self._repository.get(STAND_USER_ID)
        if user is not None:
            return user

        user = User(id=STAND_USER_ID, full_name=STAND_USER_DEFAULT_NAME)
        await self._repository.add(user)
        await self._session.commit()
        return user

    async def get_current(self) -> User:
        user = await self._repository.get(STAND_USER_ID)
        if user is None:
            raise AppError(
                "Стенд не инициализирован: пользователь не создан",
                status_code=503,
            )
        return user

    async def rename(self, full_name: str) -> User:
        user = await self.get_current()
        user.full_name = full_name
        await self._session.commit()
        return user
```

- [ ] **Step 6: Rewrite the provider**

Replace `backend/app/domains/user/provider.py`:

```python
"""DI-провайдер домена user.

CurrentUser — единственное, что домен отдаёт наружу. Сейчас он разрешается в
стендового пользователя; когда появится авторизация, меняется только этот провайдер,
а потребители (`FromDishka[CurrentUser]`) остаются прежними.
"""

from typing import NewType

from dishka import Provider, Scope, provide

from app.domains.user.models import User
from app.domains.user.repository import UserRepository
from app.domains.user.service import UserService

CurrentUser = NewType("CurrentUser", User)


class UserProvider(Provider):
    scope = Scope.REQUEST

    repository = provide(UserRepository)
    service = provide(UserService)

    @provide
    async def current_user(self, service: UserService) -> CurrentUser:
        return CurrentUser(await service.get_current())
```

- [ ] **Step 7: Seed at startup**

In `backend/app/main.py` extend the lifespan, keeping the existing comment about migrations:

```python
from app.domains.user.service import UserService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Схема БД накатывается миграциями Alembic (`alembic upgrade head`) до старта
    # сервера — см. команду запуска в deploy/docker/dev/core.yaml и Dockerfile.
    # Здесь только идемпотентный seed стендового пользователя.
    async with app.state.dishka_container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()
    yield
    await app.state.dishka_container.close()
```

- [ ] **Step 8: Drop the old write endpoints so the module still imports**

`router.py` currently calls `service.list_users()` and `service.create_user(...)`, which no longer
exist. Reduce `backend/app/domains/user/router.py` to a single read endpoint for now — Task 4 gives it
its final shape:

```python
"""HTTP-роуты стендового пользователя."""

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from app.domains.user.provider import CurrentUser
from app.domains.user.schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
@inject
async def read_me(user: FromDishka[CurrentUser]) -> UserRead:
    return UserRead.model_validate(user)
```

`schemas.py` still defines `UserRead` with `email`/`role`, so the import resolves; Task 4 replaces it.

- [ ] **Step 9: Remove password hashing**

```bash
cd backend && git rm app/core/security.py && uv remove bcrypt
```

Verify nothing references it:

Run: `grep -rn "core.security\|bcrypt\|hash_password" backend/app backend/tests backend/pyproject.toml`
Expected: no matches.

- [ ] **Step 10: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_current_user.py -v`
Expected: 5 passed.

- [ ] **Step 11: Run the whole suite and commit**

```bash
make check && make test
git add -A backend
git commit -m "feat(backend): seed stand user and expose CurrentUser via DI"
```

---

## Task 4: Endpoints, schemas, documentation

**Files:**
- Modify: `backend/app/domains/user/schemas.py`
- Modify: `backend/app/domains/user/router.py`
- Modify: `docs/architecture.md`
- Modify: `CLAUDE.md` (only if it cross-references a renumbered subsection)
- Create: `backend/tests/test_user_router.py`

**Interfaces:**
- Consumes: `CurrentUser`, `UserService`, `STAND_USER_ID`, `STAND_USER_DEFAULT_NAME` (Task 3); fixtures
  from Task 1.
- Produces: `GET /api/users/me`, `PATCH /api/users/me`, schemas `UserRead`, `UserUpdate`.

- [ ] **Step 1: Write the failing router tests**

Create `backend/tests/test_user_router.py`:

```python
"""HTTP-контракт стендового пользователя."""

from dishka import AsyncContainer
from httpx import AsyncClient

from app.domains.user.service import STAND_USER_DEFAULT_NAME, STAND_USER_ID, UserService


async def seed(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


async def test_get_me_returns_stand_user(client: AsyncClient, container: AsyncContainer) -> None:
    await seed(container)

    response = await client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["id"] == str(STAND_USER_ID)
    assert response.json()["full_name"] == STAND_USER_DEFAULT_NAME


async def test_me_response_has_no_legacy_fields(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Ни пароля, ни роли, ни email: этих понятий в MVP нет."""
    await seed(container)

    response = await client.get("/users/me")

    assert set(response.json()) == {"id", "full_name", "created_at"}


async def test_patch_me_updates_full_name(client: AsyncClient, container: AsyncContainer) -> None:
    await seed(container)

    patched = await client.patch("/users/me", json={"full_name": "Иванов И. И."})
    reread = await client.get("/users/me")

    assert patched.status_code == 200
    assert reread.json()["full_name"] == "Иванов И. И."


async def test_patch_me_rejects_blank_and_overlong_name(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """ФИО печатается в отчёте дословно — пустая строка и 300 символов недопустимы."""
    await seed(container)

    blank = await client.patch("/users/me", json={"full_name": "   "})
    overlong = await client.patch("/users/me", json={"full_name": "и" * 300})

    assert blank.status_code == 422
    assert overlong.status_code == 422


async def test_get_me_without_seed_returns_503(client: AsyncClient) -> None:
    """Миграции накатаны, seed не выполнялся — понятная 503, а не 500."""
    response = await client.get("/users/me")

    assert response.status_code == 503
    assert "не инициализирован" in response.json()["detail"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/test_user_router.py -v`
Expected: FAIL — the response still carries `email`/`role`, and `PATCH /users/me` returns 405.

- [ ] **Step 3: Rewrite the schemas**

Replace `backend/app/domains/user/schemas.py`:

```python
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
```

- [ ] **Step 4: Finish the router**

Replace `backend/app/domains/user/router.py`:

```python
"""HTTP-роуты стендового пользователя.

Регистрации и логина нет: пользователь один и создаётся при старте. Наружу торчит
только чтение и смена ФИО, которым подписываются решения инженера.
"""

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from app.domains.user.provider import CurrentUser
from app.domains.user.schemas import UserRead, UserUpdate
from app.domains.user.service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
@inject
async def read_me(user: FromDishka[CurrentUser]) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/me")
@inject
async def update_me(data: UserUpdate, service: FromDishka[UserService]) -> UserRead:
    user = await service.rename(data.full_name)
    return UserRead.model_validate(user)
```

- [ ] **Step 5: Run the router tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_user_router.py -v`
Expected: 5 passed.

- [ ] **Step 6: Document stand-mode identity**

In `docs/architecture.md`, insert a new subsection after §6.3 "Скоупы DI":

```markdown
### 6.4. Идентичность в MVP

Авторизации нет (`product.md` §14, §16). Домен `user` держит одну строку `app_user`
(`DataModel.md` §5.5) — ею подписываются создание строек и решения по гипотезам.
Строка создаётся при старте приложения идемпотентным seed'ом с фиксированным
идентификатором; ФИО правится через `PATCH /users/me`.

Остальные домены не знают, откуда взялась личность: они получают её через
`FromDishka[CurrentUser]` (`Scope.REQUEST`). Когда появится авторизация, изменится
единственный провайдер — `app/domains/user/provider.py`, а потребители нет.
```

Renumber the existing "Как добавить домен" subsection (§6.4 → §6.5) and update any cross-reference to
it in `CLAUDE.md` or elsewhere in the docs.

Run: `grep -rn "6.4\|§6" docs CLAUDE.md README.md` and fix every stale reference.

- [ ] **Step 7: Full verification**

```bash
make check
make test
cd backend && uv run alembic upgrade --sql head > /dev/null && echo "migration renders"
```

Expected: ruff clean, all tests pass (harness + model + current user + router), migration renders.

- [ ] **Step 8: Commit**

```bash
git add backend docs CLAUDE.md
git commit -m "feat(backend): stand user endpoints and architecture notes"
```
