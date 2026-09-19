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

# Локальная разработка: локальный билд + hot-reload (bind-mount исходников)
dev:
	$(COMPOSE) \
		-f $(DOCKER_FILES)/dev/core.yaml \
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

.PHONY: dev up deploy deploy-tunnel down logs pretty check
