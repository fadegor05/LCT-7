"""Разбор VLESS-ссылок и сборка конфига Xray.

Конфиг, который генерирует этот модуль, проверяется на валидность отдельно —
`xray run -test` на живом образе (см. documentation/configuration.md). Здесь
проверяется разбор ссылок и форма результата.
"""

import json

import pytest

from tools.xray_config import build_config, parse_links, vless_to_outbound

REALITY = (
    "vless://11111111-2222-3333-4444-555555555555@1.2.3.4:443"
    "?encryption=none&security=reality&sni=example.com&fp=chrome"
    "&pbk=y1KdTUcYDR7L3EoirxyEuocT0uOF2NQ9mgyU_9oALmk&sid=ab12&type=tcp"
    "&flow=xtls-rprx-vision#Узел%20один"
)
WS_TLS = (
    "vless://66666666-7777-8888-9999-000000000000@cdn.example:8443"
    "?encryption=none&security=tls&sni=cdn.example&type=ws"
    "&path=%2Fwsentry&host=cdn.example#Узел два"
)


# ---------- parse_links ----------


def test_parse_links_splits_on_commas_and_newlines() -> None:
    raw = f"{REALITY} , {WS_TLS}\n{REALITY}"

    assert parse_links(raw) == [REALITY, WS_TLS, REALITY]


def test_link_name_may_contain_spaces() -> None:
    """Клиенты выдают «#Узел два» без кодирования пробела — ссылка не должна рваться."""
    assert parse_links(WS_TLS) == [WS_TLS]
    assert WS_TLS.endswith("#Узел два")


def test_several_links_in_one_line_are_rejected() -> None:
    """Иначе вторая ссылка уехала бы в название первой и молча не работала."""
    with pytest.raises(ValueError, match="несколько ссылок"):
        parse_links(f"{REALITY} {WS_TLS}")


def test_parse_links_ignores_blank_input() -> None:
    assert parse_links("") == []
    assert parse_links("   \n ,, \t ") == []


def test_parse_links_rejects_non_vless_schemes() -> None:
    """Молча пропустить чужую ссылку нельзя: канал будет «настроен», а трафик не пойдёт."""
    with pytest.raises(ValueError, match="vless://"):
        parse_links("ss://whatever@host:443")


# ---------- vless_to_outbound ----------


def test_reality_outbound() -> None:
    outbound = vless_to_outbound(REALITY, tag="proxy-0")

    assert outbound["tag"] == "proxy-0"
    assert outbound["protocol"] == "vless"
    vnext = outbound["settings"]["vnext"][0]
    assert (vnext["address"], vnext["port"]) == ("1.2.3.4", 443)
    assert vnext["users"][0]["id"] == "11111111-2222-3333-4444-555555555555"
    assert vnext["users"][0]["encryption"] == "none"
    assert vnext["users"][0]["flow"] == "xtls-rprx-vision"
    stream = outbound["streamSettings"]
    assert stream["network"] == "tcp"
    assert stream["security"] == "reality"
    assert stream["realitySettings"] == {
        "serverName": "example.com",
        "fingerprint": "chrome",
        "publicKey": "y1KdTUcYDR7L3EoirxyEuocT0uOF2NQ9mgyU_9oALmk",
        "shortId": "ab12",
    }


def test_ws_tls_outbound() -> None:
    outbound = vless_to_outbound(WS_TLS, tag="proxy-1")

    stream = outbound["streamSettings"]
    assert stream["network"] == "ws"
    assert stream["security"] == "tls"
    assert stream["tlsSettings"] == {"serverName": "cdn.example"}
    # Путь в ссылке закодирован (%2F) — в конфиг должен попасть раскодированным.
    # host отдельным полем: форма headers.Host объявлена устаревшей в Xray 26.
    assert stream["wsSettings"] == {"path": "/wsentry", "host": "cdn.example"}
    # Без flow ключа быть не должно: пустая строка ломает подключение
    assert "flow" not in outbound["settings"]["vnext"][0]["users"][0]


def test_sni_falls_back_to_host_when_absent() -> None:
    link = "vless://11111111-2222-3333-4444-555555555555@tls.example:443?security=tls&type=tcp"

    stream = vless_to_outbound(link, tag="proxy-0")["streamSettings"]

    assert stream["tlsSettings"]["serverName"] == "tls.example"


def test_alpn_is_split_into_a_list() -> None:
    link = (
        "vless://11111111-2222-3333-4444-555555555555@tls.example:443"
        "?security=tls&type=tcp&alpn=h2%2Chttp%2F1.1"
    )

    stream = vless_to_outbound(link, tag="proxy-0")["streamSettings"]

    assert stream["tlsSettings"]["alpn"] == ["h2", "http/1.1"]


def test_grpc_outbound() -> None:
    link = (
        "vless://11111111-2222-3333-4444-555555555555@grpc.example:443"
        "?security=tls&type=grpc&serviceName=tunnel&mode=multi"
    )

    stream = vless_to_outbound(link, tag="proxy-0")["streamSettings"]

    assert stream["network"] == "grpc"
    assert stream["grpcSettings"] == {"serviceName": "tunnel", "multiMode": True}


def test_httpupgrade_outbound() -> None:
    link = (
        "vless://11111111-2222-3333-4444-555555555555@up.example:443"
        "?security=tls&type=httpupgrade&path=%2Fup&host=up.example"
    )

    stream = vless_to_outbound(link, tag="proxy-0")["streamSettings"]

    assert stream["network"] == "httpupgrade"
    assert stream["httpupgradeSettings"] == {"path": "/up", "host": "up.example"}


def test_plain_tcp_without_security() -> None:
    link = "vless://11111111-2222-3333-4444-555555555555@plain.example:80?type=tcp"

    stream = vless_to_outbound(link, tag="proxy-0")["streamSettings"]

    assert stream["security"] == "none"
    assert "tlsSettings" not in stream
    assert "realitySettings" not in stream


# ---------- отказы с понятным текстом ----------


def test_reality_without_public_key_is_rejected() -> None:
    """Xray примет конфиг, но соединение не встанет — ловим на генерации."""
    link = (
        "vless://11111111-2222-3333-4444-555555555555@1.2.3.4:443"
        "?security=reality&sni=example.com&type=tcp"
    )

    with pytest.raises(ValueError, match="pbk"):
        vless_to_outbound(link, tag="proxy-0")


def test_unknown_transport_is_rejected() -> None:
    link = "vless://11111111-2222-3333-4444-555555555555@1.2.3.4:443?security=tls&type=quic"

    with pytest.raises(ValueError, match="quic"):
        vless_to_outbound(link, tag="proxy-0")


def test_unknown_security_is_rejected() -> None:
    link = "vless://11111111-2222-3333-4444-555555555555@1.2.3.4:443?security=xtls&type=tcp"

    with pytest.raises(ValueError, match="xtls"):
        vless_to_outbound(link, tag="proxy-0")


def test_link_without_uuid_is_rejected() -> None:
    with pytest.raises(ValueError, match="идентификатор"):
        vless_to_outbound("vless://@1.2.3.4:443?type=tcp", tag="proxy-0")


def test_link_without_port_is_rejected() -> None:
    with pytest.raises(ValueError, match="порт"):
        vless_to_outbound(
            "vless://11111111-2222-3333-4444-555555555555@1.2.3.4?type=tcp", tag="proxy-0"
        )


def test_grpc_without_service_name_is_rejected() -> None:
    link = "vless://11111111-2222-3333-4444-555555555555@1.2.3.4:443?security=tls&type=grpc"

    with pytest.raises(ValueError, match="serviceName"):
        vless_to_outbound(link, tag="proxy-0")


# ---------- build_config ----------


def test_config_has_http_inbound_and_one_outbound_per_link() -> None:
    config = build_config([REALITY, WS_TLS], inbound_port=8080)

    assert config["inbounds"][0]["protocol"] == "http"
    assert config["inbounds"][0]["port"] == 8080
    tags = [out["tag"] for out in config["outbounds"]]
    assert tags[:2] == ["proxy-0", "proxy-1"]


def test_config_balances_across_all_links() -> None:
    """Смысл всей затеи: несколько ссылок, живую выбирает Xray."""
    config = build_config([REALITY, WS_TLS], inbound_port=8080)

    balancer = config["routing"]["balancers"][0]
    assert balancer["selector"] == ["proxy-"]
    assert balancer["strategy"]["type"] == "leastPing"
    assert config["routing"]["rules"][0]["balancerTag"] == balancer["tag"]
    assert config["observatory"]["subjectSelector"] == ["proxy-"]


def test_config_probes_telegram_by_default() -> None:
    config = build_config([REALITY], inbound_port=8080)

    assert "api.telegram.org" in config["observatory"]["probeUrl"]


def test_single_link_still_goes_through_the_balancer() -> None:
    """Одна ссылка — тот же путь, иначе поведение зависело бы от их числа."""
    config = build_config([REALITY], inbound_port=8080)

    assert config["routing"]["rules"][0]["balancerTag"] == "proxy-balancer"


def test_config_without_links_is_rejected() -> None:
    with pytest.raises(ValueError, match="XRAY__LINKS"):
        build_config([], inbound_port=8080)


def test_config_is_json_serialisable() -> None:
    json.dumps(build_config([REALITY, WS_TLS], inbound_port=8080))
