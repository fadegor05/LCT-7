"""Настройки уведомлений: без токена канал считается ненастроенным."""

from app.core.settings import NotifySettings, Settings


def test_telegram_not_configured_by_default() -> None:
    settings = NotifySettings()

    assert settings.telegram.token is None
    assert settings.telegram_configured is False


def test_telegram_configured_requires_both_token_and_username() -> None:
    """Ссылку t.me собрать не из чего, если нет имени бота — считаем ненастроенным."""
    only_token = NotifySettings.model_validate({"telegram": {"token": "123:abc"}})
    both = NotifySettings.model_validate(
        {"telegram": {"token": "123:abc", "bot_username": "lct7_bot"}}
    )

    assert only_token.telegram_configured is False
    assert both.telegram_configured is True


def test_settings_exposes_notify_section() -> None:
    assert isinstance(Settings().notify, NotifySettings)


def test_public_url_strips_trailing_slash() -> None:
    """Ссылки склеиваются конкатенацией — двойной слеш в URL недопустим."""
    settings = NotifySettings.model_validate({"public_url": "https://example.com/"})

    assert settings.public_url == "https://example.com"


def test_telegram_proxy_is_empty_by_default() -> None:
    """Прокси нужен не всем: по умолчанию бот ходит напрямую."""
    assert NotifySettings().telegram.proxy_url is None


def test_telegram_proxy_is_read_from_settings() -> None:
    settings = NotifySettings.model_validate({"telegram": {"proxy_url": "http://xray:8080"}})

    assert settings.telegram.proxy_url == "http://xray:8080"
