DOCKER_FILES = ./deploy/docker

COMPOSE = docker compose \
	--project-directory . \
	--env-file ./.env \
	--env-file ./deploy/versions.env \
	-f $(DOCKER_FILES)/common/core.yaml \
	-f $(DOCKER_FILES)/common/infra.yaml

PROD = $(COMPOSE) \
	-f $(DOCKER_FILES)/prod/core.yaml

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

down:
	$(COMPOSE) down --remove-orphans

logs:
	$(COMPOSE) logs -f

.PHONY: dev up deploy down logs
