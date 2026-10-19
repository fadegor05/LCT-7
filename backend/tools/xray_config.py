"""Сборка конфига Xray из списка VLESS-ссылок.

Запускается init-контейнером перед Xray (deploy/docker/common/proxy.yaml):

    python tools/xray_config.py --out /config/config.json

Ссылки берутся из XRAY__LINKS — через запятую, пробел или перевод строки.
Каждая становится отдельным outbound'ом `proxy-<n>`; живую среди них выбирает
сам Xray: observatory пингует все, балансировщик со стратегией leastPing шлёт
трафик через самую быструю из отвечающих и переключается, когда она падает.

Незнакомый параметр ссылки — это отказ с понятным текстом, а не outbound
«на авось»: иначе канал считался бы настроенным, а трафик бы не шёл, и причину
пришлось бы искать в логах Xray.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

# Префикс тегов outbound'ов. По нему же observatory и балансировщик находят
# подопечных, поэтому он должен совпадать в трёх местах.
TAG_PREFIX = "proxy-"
BALANCER_TAG = "proxy-balancer"

# Что пингуем, чтобы считать ссылку живой. Именно телеграм: ссылка может
# работать «вообще», но быть заблокированной именно до api.telegram.org.
DEFAULT_PROBE_URL = "https://api.telegram.org/"
DEFAULT_PROBE_INTERVAL = "10s"

SUPPORTED_SECURITY = ("none", "tls", "reality")
SUPPORTED_NETWORK = ("tcp", "ws", "grpc", "httpupgrade")

# Делим только по переводам строк и запятым. По пробелам нельзя: клиенты
# выдают ссылки с незакодированным названием в #fragment («#Узел два»), и
# дробление по пробелу разорвало бы такую ссылку пополам.
_SPLIT = re.compile(r"[\n\r,]+")


def parse_links(raw: str) -> list[str]:
    """Разбить XRAY__LINKS на отдельные ссылки."""
    links = [part.strip() for part in _SPLIT.split(raw) if part.strip()]
    for link in links:
        if not link.startswith("vless://"):
            raise ValueError(
                f"Поддерживаются только ссылки vless://, получено: {link[:16]}… "
                "Остальные протоколы в XRAY__LINKS не разбираются."
            )
        if link.count("vless://") > 1:
            raise ValueError(
                "В одной строке несколько ссылок. Разделяйте их переводом строки "
                "или запятой: по пробелам делить нельзя, пробел бывает в названии узла."
            )
    return links


def _one(params: dict[str, list[str]], name: str) -> str | None:
    """Первое значение параметра запроса или None."""
    values = params.get(name)
    if not values:
        return None
    value = unquote(values[0]).strip()
    return value or None


def _stream_settings(link: str, params: dict[str, list[str]], host: str) -> dict[str, Any]:
    """streamSettings: транспорт и шифрование, как их описывает ссылка."""
    security = (_one(params, "security") or "none").lower()
    if security not in SUPPORTED_SECURITY:
        raise ValueError(
            f"Ссылка {link[:32]}…: неизвестный security={security}. "
            f"Поддерживаются: {', '.join(SUPPORTED_SECURITY)}"
        )

    network = (_one(params, "type") or "tcp").lower()
    if network not in SUPPORTED_NETWORK:
        raise ValueError(
            f"Ссылка {link[:32]}…: неизвестный транспорт type={network}. "
            f"Поддерживаются: {', '.join(SUPPORTED_NETWORK)}"
        )

    stream: dict[str, Any] = {"network": network, "security": security}
    # Имя сервера для TLS: sni, а если его нет — адрес узла
    server_name = _one(params, "sni") or host
    fingerprint = _one(params, "fp")
    alpn = _one(params, "alpn")

    if security == "reality":
        public_key = _one(params, "pbk")
        if not public_key:
            raise ValueError(
                f"Ссылка {link[:32]}…: для security=reality обязателен публичный ключ pbk"
            )
        reality: dict[str, Any] = {"serverName": server_name, "publicKey": public_key}
        if fingerprint:
            reality["fingerprint"] = fingerprint
        short_id = _one(params, "sid")
        if short_id:
            reality["shortId"] = short_id
        spider = _one(params, "spx")
        if spider:
            reality["spiderX"] = spider
        stream["realitySettings"] = reality
    elif security == "tls":
        tls: dict[str, Any] = {"serverName": server_name}
        if fingerprint:
            tls["fingerprint"] = fingerprint
        if alpn:
            tls["alpn"] = [item.strip() for item in alpn.split(",") if item.strip()]
        stream["tlsSettings"] = tls

    if network == "ws":
        ws: dict[str, Any] = {"path": _one(params, "path") or "/"}
        ws_host = _one(params, "host")
        if ws_host:
            # Отдельное поле host, а не headers.Host: вторая форма объявлена
            # устаревшей и Xray 26 пишет об этом предупреждение при старте
            ws["host"] = ws_host
        stream["wsSettings"] = ws
    elif network == "httpupgrade":
        upgrade: dict[str, Any] = {"path": _one(params, "path") or "/"}
        upgrade_host = _one(params, "host")
        if upgrade_host:
            upgrade["host"] = upgrade_host
        stream["httpupgradeSettings"] = upgrade
    elif network == "grpc":
        service_name = _one(params, "serviceName")
        if not service_name:
            raise ValueError(f"Ссылка {link[:32]}…: для type=grpc обязателен serviceName")
        stream["grpcSettings"] = {
            "serviceName": service_name,
            "multiMode": (_one(params, "mode") or "").lower() == "multi",
        }

    return stream


def vless_to_outbound(link: str, tag: str) -> dict[str, Any]:
    """Превратить одну VLESS-ссылку в outbound Xray."""
    parts = urlsplit(link)
    user_id = unquote(parts.username or "").strip()
    if not user_id:
        raise ValueError(f"Ссылка {link[:32]}…: не указан идентификатор пользователя (UUID)")
    host = parts.hostname
    if not host:
        raise ValueError(f"Ссылка {link[:32]}…: не указан адрес узла")
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError(f"Ссылка {link[:32]}…: некорректный порт") from error
    if not port:
        raise ValueError(f"Ссылка {link[:32]}…: не указан порт")

    params = parse_qs(parts.query, keep_blank_values=False)
    user: dict[str, Any] = {"id": user_id, "encryption": "none"}
    flow = _one(params, "flow")
    if flow:
        # Пустое значение flow ломает подключение, поэтому ключа или нет, или он значимый
        user["flow"] = flow

    return {
        "tag": tag,
        "protocol": "vless",
        "settings": {"vnext": [{"address": host, "port": port, "users": [user]}]},
        "streamSettings": _stream_settings(link, params, host),
    }


def build_config(
    links: list[str],
    *,
    inbound_port: int,
    probe_url: str = DEFAULT_PROBE_URL,
    probe_interval: str = DEFAULT_PROBE_INTERVAL,
) -> dict[str, Any]:
    """Собрать конфиг: HTTP-вход, по outbound'у на ссылку, балансировщик поверх.

    Маршрутизации по домену нет намеренно: в этот прокси попадает только то, что
    послал телеграм-клиент бэкенда, остальной трафик приложения идёт напрямую.
    """
    if not links:
        raise ValueError(
            "Список ссылок пуст: задайте XRAY__LINKS в .env "
            "(ссылки vless:// через запятую или перевод строки)"
        )

    outbounds = [
        vless_to_outbound(link, tag=f"{TAG_PREFIX}{index}") for index, link in enumerate(links)
    ]
    outbounds.append({"tag": "direct", "protocol": "freedom"})
    outbounds.append({"tag": "block", "protocol": "blackhole"})

    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "http-in",
                "listen": "0.0.0.0",
                "port": inbound_port,
                "protocol": "http",
                "sniffing": {"enabled": True, "destOverride": ["http", "tls"]},
            }
        ],
        "outbounds": outbounds,
        "observatory": {
            "subjectSelector": [TAG_PREFIX],
            "probeUrl": probe_url,
            "probeInterval": probe_interval,
        },
        "routing": {
            "domainStrategy": "AsIs",
            "balancers": [
                {
                    "tag": BALANCER_TAG,
                    "selector": [TAG_PREFIX],
                    "strategy": {"type": "leastPing"},
                }
            ],
            "rules": [{"type": "field", "network": "tcp,udp", "balancerTag": BALANCER_TAG}],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Собрать конфиг Xray из XRAY__LINKS")
    parser.add_argument("--out", required=True, help="Куда записать config.json")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("XRAY__HTTP_PORT", "8080")),
        help="Порт HTTP-входа внутри сети compose",
    )
    parser.add_argument(
        "--probe-url",
        default=os.environ.get("XRAY__PROBE_URL", DEFAULT_PROBE_URL),
        help="Что пингуют, чтобы считать ссылку живой",
    )
    parser.add_argument(
        "--probe-interval",
        default=os.environ.get("XRAY__PROBE_INTERVAL", DEFAULT_PROBE_INTERVAL),
        help="Как часто пинговать",
    )
    args = parser.parse_args(argv)

    try:
        links = parse_links(os.environ.get("XRAY__LINKS", ""))
        config = build_config(
            links,
            inbound_port=args.port,
            probe_url=args.probe_url,
            probe_interval=args.probe_interval,
        )
    except ValueError as error:
        # Контейнер должен упасть громко: молчаливый запуск без прокси хуже отказа
        print(f"Конфиг Xray не собран: {error}", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Сами ссылки не печатаем: в них учётные данные
    print(f"Конфиг Xray собран: {len(links)} ссылок -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
