DOCKER_FILES = ./deploy/docker

COMPOSE = docker compose \
	--project-directory . \
	--env-file ./.env \
	--env-file ./deploy/versions.env \
	-f $(DOCKER_FILES)/common/core.yaml \
	-f $(DOCKER_FILES)/common/infra.yaml

PROD = $(COMPOSE) \
	-f $(DOCKER_FILES)/prod/core.yaml

# Прод за туннелем TUNA: TLS на стороне туннеля, внутрь идёт HTTP (deploy/README.md)
TUNNEL = $(COMPOSE) \
	-f $(DOCKER_FILES)/prod/tunnel.yaml

# Прод с прокси для телеграма: в России api.telegram.org заблокирован.
# Нужен XRAY__LINKS в .env, иначе xray-init упадёт с понятной ошибкой.
PROXY = $(PROD) \
	-f $(DOCKER_FILES)/common/proxy.yaml

# Загрузка весов детектора из приватного репозитория HuggingFace
# Требует переменной окружения HF_TOKEN (HuggingFace токен с доступом к Gatarez/lct7-construction-detector)
ml-weights:
	$(COMPOSE) run --rm --no-deps -e HF_TOKEN -v lct7_ml_weights:/weights-rw ml python tools/fetch_weights.py --out /weights-rw

# Локальная разработка: локальный билд + hot-reload (bind-mount исходников)
dev:
	$(COMPOSE) \
		-f $(DOCKER_FILES)/dev/core.yaml \
		up --build -d

# Локальная разработка с прокси для телеграма (профиль proxy).
# Нужен XRAY__LINKS в .env — одна или несколько ссылок vless://.
dev-proxy:
	$(COMPOSE) \
		-f $(DOCKER_FILES)/common/proxy.yaml \
		-f $(DOCKER_FILES)/dev/core.yaml \
		--profile proxy \
		up --build -d

# Прод с прокси для телеграма (профиль proxy), без сборки и без pull
up-proxy:
	$(PROXY) --profile proxy up -d --no-build

# Тянем образы по тегам и поднимаем прод вместе с прокси — то же, что deploy, но с Xray
deploy-proxy:
	$(PROXY) --profile proxy pull
	$(PROXY) --profile proxy up -d --no-build

# То же за туннелем
deploy-tunnel-proxy:
	$(TUNNEL) -f $(DOCKER_FILES)/common/proxy.yaml --profile proxy pull
	$(TUNNEL) -f $(DOCKER_FILES)/common/proxy.yaml --profile proxy up -d --no-build

# Проверить, что из XRAY__LINKS собирается конфиг, который принимает сам Xray
xray-check:
	$(COMPOSE) -f $(DOCKER_FILES)/common/proxy.yaml --profile proxy run --rm --no-deps xray-init
	docker run --rm -v lct-7_xray_config:/cfg:ro ghcr.io/xtls/xray-core:26.3.27 \
		run -test -c /cfg/config.json

# Локальная разработка с ML-детектором (включает профиль ml)
dev-ml:
	$(COMPOSE) \
		-f $(DOCKER_FILES)/dev/core.yaml \
		--profile ml \
		up --build -d

# Прод: тянем готовые образы по тегам из deploy/versions.env, не билдим
up:
	$(PROD) up -d --no-build

deploy:
	$(PROD) pull
	$(PROD) up -d --no-build

# То же, но для хоста за туннелем (xxprod.ru через TUNA)
deploy-tunnel:
	$(TUNNEL) pull
	$(TUNNEL) up -d --no-build

down:
	$(COMPOSE) down --remove-orphans

logs:
	$(COMPOSE) logs -f

# Автоформат + автофиксы линтера (ruff)
pretty:
	cd backend && uv run ruff format . && uv run ruff check --fix .

# Проверка без изменений (для CI / pre-commit)
check:
	cd backend && uv run ruff check . && uv run ruff format --check .

# Тесты бэкенда
test:
	cd backend && uv run pytest

# Frontend: автоформат + автофиксы (Prettier, ESLint, Stylelint)
front-pretty:
	cd frontend && pnpm run format && pnpm run lint:fix

# Frontend: проверки без изменений (типы, линтеры, формат, тесты с порогами покрытия)
front-check:
	cd frontend && pnpm run check

# Frontend: тесты с отчётом покрытия (frontend/coverage/index.html)
front-test:
	cd frontend && pnpm run test:coverage

.PHONY: ml-weights dev dev-ml dev-proxy up up-proxy xray-check deploy deploy-proxy deploy-tunnel deploy-tunnel-proxy down logs pretty check test front-pretty front-check front-test
