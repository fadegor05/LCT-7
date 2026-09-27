"""Модель соответствует docs/DataModel.md §5.5: таблица app_user, только id и ФИО."""

from app.domains.user.models import User


def test_table_is_app_user() -> None:
    assert User.__tablename__ == "app_user"


def test_columns_match_data_model() -> None:
    assert set(User.__table__.columns.keys()) == {"id", "full_name", "created_at"}


def test_no_auth_columns_remain() -> None:
    """Пароля, роли и email в MVP нет — см. product.md §14, §16."""
    assert set(User.__table__.columns.keys()).isdisjoint(
        {"email", "role", "hashed_password", "name"}
    )
