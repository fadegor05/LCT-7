# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

LCT-7 is a hackathon monorepo for an automated construction-site violation detection service
(ДГП Москвы case). Three independent parts:

- `backend/` — FastAPI + Dishka (DI) + Granian (ASGI) + SQLAlchemy async + PostgreSQL, Alembic migrations.
- `frontend/` — React 19 + Vite 6 + TypeScript, React Router, TanStack Query, Zod, CSS Modules; MSW mocks; served by nginx in prod.
- `ml/` — vision/LLM service (YOLO26-m detector, stamp reader, assistant, schedule parsing) plus research and CLI tools. The backend calls it over HTTP via `DETECTOR__URL`; with the URL empty the detector is off and photos stay `pending`.

Orchestration is Docker Compose with layered files (`common` / `dev` / `prod`) behind Traefik.
`makefile` at the root is the entry point. Much of the code documentation is in Russian.

## Skills

`.claude/skills/` contains the [obra/superpowers](https://github.com/obra/superpowers) skill set
(imported, MIT-licensed) — brainstorming, writing/executing plans, TDD, systematic debugging,
subagent-driven development, code review, git worktrees, etc. Claude Code should check
`.claude/skills/using-superpowers/SKILL.md` for how and when to invoke them.

## Commands

Root (Docker Compose via `makefile`):

```bash
cp .env.dist .env   # first-time setup
make dev            # local: build + bind-mount + hot-reload (backend --reload, Vite dev-server)
make up             # prod images, no build
make deploy         # pull prod images by tag (deploy/versions.env) + up
make deploy-tunnel  # same, but for a host behind a tunnel (TLS terminated upstream)
make down           # stop, remove orphans
make logs           # follow logs
make pretty         # backend: ruff format + ruff check --fix
make check          # backend: ruff check + ruff format --check (CI/pre-commit)
make front-pretty   # frontend: prettier + eslint --fix + stylelint --fix
make front-check    # frontend: tsc + eslint + stylelint + prettier --check + vitest with coverage thresholds
make front-test     # frontend: vitest with coverage report
```

In `frontend/`: `pnpm dev` (mocks on by default via `.env.development`), `pnpm dev:api` (real backend),
`pnpm test`, `pnpm lint`, `pnpm check`.

## Backend structure

- `app/core/` — infrastructure: `settings.py`, `database.py` (`Base`), `repository.py` (`BaseRepository`), `rate_limit.py`.
- `app/plugins/` — cross-cutting: `di.py`, `routing.py`, `exceptions.py`.
- `app/adapters/` — external systems (ML, ГЭСН reference data).
- `app/domains/<domain>/` — one domain = one flat directory with `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`, `provider.py` (omit files a domain doesn't need). `core/`, `plugins/`, `adapters/` are not domains.
- `app/models.py` — single import point for ORM models, so Alembic autogenerate sees them.
- DI: `Scope.APP` — settings, engine, sessionmaker, external clients, stateless parsers, reference caches. `Scope.REQUEST` — session, repositories, services.

Full convention: `.claude/rules/backend/architecture.md`.

## Frontend structure

- `src/api/` — `client.ts` (`request()` validates every response with a Zod schema), `schemas.ts` (Zod copy of the backend Pydantic schemas and enums), one file per domain with API functions and TanStack Query hooks; cache keys in `keys.ts` (`['site', id, …]`, any input edit invalidates the whole site).
- `src/components/ui/` — LCT-7 design system (tokens in `src/styles/tokens.css`); `components/layout/` — app shell, `SiteShell` with site tabs.
- `src/features/<domain>/` — composite components per screen; `src/pages/` — one page per mockup screen, routes in `src/app/routes.tsx`.
- `src/mocks/` — MSW handlers over an in-memory db (`db.ts`); toggled by `VITE_USE_MOCKS`. Same handlers run in tests (`src/test/setup.ts`).
- Tests sit next to code (`*.test.tsx`); pages are tested through `renderRoute(url)`. Every new component needs a test; coverage thresholds live in `vite.config.ts`.

Frontend architecture is described in the structure list above and in `documentation/architecture.md`.

## Documentation

`documentation/` describes what is implemented (architecture, data model, API, business logic, install/run,
configuration, limitations). `docs/superpowers/` holds design specs and plans for individual features.
