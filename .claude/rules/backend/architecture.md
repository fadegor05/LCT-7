---
paths:
  - "backend/**/*.py"
---

**Dependency injection (Dishka).** Infrastructure providers (`Settings`, `AsyncEngine`, `async_sessionmaker` at `Scope.APP`; `AsyncSession` at `Scope.REQUEST`) live in `app/plugins/di.py`. Each domain has its own `Provider` in `modules/<domain>/provider.py` (repository + service, `Scope.REQUEST`). Routes receive dependencies via `FromDishka[...]` + `@inject`. Constructors are wired automatically by type.

- `app/core/` — infrastructure: `settings.py` (pydantic-settings, nested env via `__` e.g. `POSTGRES__HOST`), `database.py` (`Base`), `security.py` (bcrypt).
- `app/plugins/` — cross-cutting: `di.py` (Dishka container), `exceptions.py`, `routing.py`.
- `app/modules/<domain>/` — one folder per domain, each with `models.py / schemas.py / repository.py / service.py / provider.py / router.py`.
- `app/adapters/` — external integrations (ML client planned).

**Request flow.** router → service (business logic, raises `AppError(message, status_code)`) → repository (SQLAlchemy queries). The service owns the `AsyncSession` and calls `commit()`; repositories only stage changes.

**Repositories.** Every domain repository MUST inherit from `BaseRepository[Model]` (`app/core/repository.py`) and set the `model` class attribute. Base provides the common queries (`list`, `get`, `get_by`, `list_by`, `add`, `delete`, `delete_by`). Add only domain-specific queries in the subclass, or override a base method when the model needs different behaviour (e.g. custom ordering).

**Error handling.** Services raise `AppError` from `app/plugins/exceptions.py`; a single handler (registered in `main.py`) maps it to a JSON `{"detail": ...}` response.

**Adapters.** In case using some external service, like storage (ex. Amazon S3), kv database (ex. Redis), use pattern Adapter with Protocol class and determined or simple implementation inherited from that

**Schemas.** We build schemas content in routers, from services we return models 

### Adding a new domain module

1. Create `app/modules/<domain>/` with the six files above (copy `user/` as the template).
2. Register its router in `app/plugins/routing.py`.
3. Register its provider in `create_container()` in `app/plugins/di.py`.
4. Import its `models` in `app/models.py` — **Alembic autogenerate only sees models imported there.**
5. Generate a migration: `uv run alembic revision --autogenerate -m "..."`.

Schema is applied by `alembic upgrade head` at container start (see `deploy/docker/dev/core.yaml`), **not** by `create_all` — the lifespan hook does not create tables.
