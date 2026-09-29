#!/usr/bin/env bash
# Автодеплой стенда: ВМ сама забирает обновления из Yandex Container Registry.
#
# Входящие соединения с зарубежных адресов до ВМ в Yandex Cloud не доходят, а
# api.github.com с ВМ недоступен, поэтому ни деплой по SSH из GitHub Actions, ни
# self-hosted runner здесь не работают. Вместо этого systemd-таймер раз в две
# минуты запускает этот скрипт:
#   1. тянет образ-«посылку» deploy:latest и читает из метки коммит, из которого
#      она собрана (CD публикует её последней, когда образы сервисов уже в реестре);
#   2. если коммит новый — раскладывает makefile и deploy/ в /opt/veha, ставит
#      теги sha-<коммит> и делает make $DEPLOY_TARGET (из .env ВМ, по умолчанию
#      deploy-tunnel; для домена с TLS — DEPLOY_TARGET=deploy);
#   3. проверяет /api/health и запоминает коммит, чтобы не деплоить его повторно.
#
# Журнал: journalctl -u veha-autodeploy. Установка — deploy/README.md.
set -euo pipefail

DIR=/opt/veha
# Реестр берётся из versions.env текущей выкладки: первая лежит на ВМ с установки.
REGISTRY=$(sed -n "s/^REGISTRY=//p" "$DIR/deploy/versions.env")
BUNDLE="$REGISTRY/deploy:latest"
STATE="$DIR/.deployed-revision"

# Таймер не запустит второй экземпляр, но ручной запуск во время деплоя — может.
exec 9>/tmp/veha-autodeploy.lock
flock -n 9 || exit 0

docker pull -q "$BUNDLE" >/dev/null
REV=$(docker image inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$BUNDLE")
if [ -z "$REV" ]; then
  echo "у посылки нет метки org.opencontainers.image.revision" >&2
  exit 1
fi
if [ "$REV" = "$(cat "$STATE" 2>/dev/null || true)" ]; then
  exit 0
fi

TAG="sha-${REV:0:7}"
echo "деплой коммита $REV (теги $TAG)"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
CID=$(docker create "$BUNDLE" true)
docker cp "$CID:/bundle/." "$TMP/"
docker rm "$CID" >/dev/null

# Цель make берётся из .env ВМ: при переходе на домен с TLS там ставят
# DEPLOY_TARGET=deploy, иначе каждый автодеплой возвращал бы стенд в режим
# туннеля (HTTP на :80, без Host и сертификатов).
DEPLOY_TARGET=$(sed -n "s/^DEPLOY_TARGET=//p" "$DIR/.env" | tr -d "\"' ")
DEPLOY_TARGET=${DEPLOY_TARGET:-deploy-tunnel}
case "$DEPLOY_TARGET" in
  deploy|deploy-tunnel) ;;
  *) echo "DEPLOY_TARGET=$DEPLOY_TARGET: ожидается deploy или deploy-tunnel" >&2; exit 1 ;;
esac

# cp без удаления: .env и acme.json на ВМ не трогаются. traefik.yml — конфиг
# хоста (email ACME и т.п.): кладётся только если его ещё нет, локальные правки
# на ВМ не перетираются.
cp "$TMP/makefile" "$DIR/makefile"
TRAEFIK_YML=deploy/config/traefik/traefik.yml
if [ -f "$DIR/$TRAEFIK_YML" ]; then
  rm -f "$TMP/$TRAEFIK_YML"
fi
cp -r "$TMP/deploy/." "$DIR/deploy/"
sed -i "s|^BACKEND_TAG=.*|BACKEND_TAG=$TAG|;s|^FRONTEND_TAG=.*|FRONTEND_TAG=$TAG|;s|^ML_TAG=.*|ML_TAG=$TAG|" \
  "$DIR/deploy/versions.env"

# Скрипт обновляет свою копию из посылки: иначе правки в репозитории до ВМ не
# доходят (так 28.09 на ВМ остался старый скрипт с затиранием traefik.yml).
# Копия через mv — атомарная замена файла, текущий запуск читает старый inode.
if [ -f "$DIR/deploy/autodeploy/autodeploy.sh" ]; then
  cp "$DIR/deploy/autodeploy/autodeploy.sh" "$DIR/bin/.autodeploy.sh.new"
  chmod 755 "$DIR/bin/.autodeploy.sh.new"
  mv "$DIR/bin/.autodeploy.sh.new" "$DIR/bin/autodeploy.sh"
fi

cd "$DIR"
make "$DEPLOY_TARGET"

# Коммит запоминается и при красном смоуке: иначе таймер будет передеплоивать
# сломанную версию каждые две минуты. Починка — новый коммит в main.
echo "$REV" > "$STATE"
docker image prune -f >/dev/null

# С доменом (DEPLOY_TARGET=deploy) Traefik маршрутизирует по Host и на localhost
# отвечает 404, поэтому проверяем по имени домена, но стучимся на эту же машину.
# -k: проверяется приложение, а не сертификат (до выпуска он самоподписанный).
DOMAIN=$(sed -n "s/^DOMAIN=//p" "$DIR/.env" | tr -d "\"' ")
if [ "$DEPLOY_TARGET" = deploy ] && [ -n "$DOMAIN" ]; then
  HEALTH_CMD=(curl -fsSk -o /dev/null --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/api/health")
else
  HEALTH_CMD=(curl -fsS -o /dev/null http://localhost/api/health)
fi

for _ in $(seq 1 30); do
  if "${HEALTH_CMD[@]}"; then
    echo "готово: $REV, /api/health отвечает"
    exit 0
  fi
  sleep 5
done
echo "коммит $REV выкачен, но /api/health не отвечает" >&2
exit 1
