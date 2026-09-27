# «Посылка» с compose-файлами для стенда: makefile и deploy/ того коммита, из
# которого собраны образы. ВМ забирает её из реестра вместе с образами сервисов,
# поэтому ей не нужен доступ к репозиторию. Контекст сборки — корень репозитория,
# лишнее отсекает Dockerfile.dockerignore рядом.
FROM busybox:1.36
COPY makefile /bundle/makefile
COPY deploy /bundle/deploy
