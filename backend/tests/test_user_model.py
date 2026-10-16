"""Модель соответствует docs/DataModel.md §5.5: таблица app_user с аутентификацией."""

from app.domains.user.models import User


def test_table_is_app_user() -> None:
    assert User.__tablename__ == "app_user"


def test_columns_match_data_model() -> None:
    assert set(User.__table__.columns.keys()) == {
        "id",
        "full_name",
        "login",
        "password_hash",
        "created_at",
    }


def test_no_legacy_auth_columns() -> None:
    """Роли и email в MVP нет — см. product.md §14, §16."""
    assert set(User.__table__.columns.keys()).isdisjoint(
        {"email", "role", "hashed_password", "name"}
    )
