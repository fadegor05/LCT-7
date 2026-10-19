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
