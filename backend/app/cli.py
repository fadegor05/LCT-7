"""CLI команды для управления приложением."""

import asyncio
import getpass
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.domains.user.models import User
from app.domains.user.security import hash_password
from app.plugins.exceptions import AppError


async def create_user(
    session_factory: async_sessionmaker[AsyncSession],
    login: str,
    full_name: str | None,
    password: str,
) -> User:
    """Создать пользователя с логином и паролем.

    Args:
        session_factory: Фабрика сессий.
        login: Логин пользователя (будет преобразован в нижний регистр и срезаны пробелы).
        full_name: ФИО пользователя (опционально).
        password: Пароль (непустой).

    Returns:
        Созданный пользователь.

    Raises:
        AppError с exit code 1 если логин занят.
    """
    login_lower = login.strip().lower()
    if not login_lower or not password:
        raise AppError("Логин и пароль не могут быть пустыми", status_code=400)

    async with session_factory() as session:
        existing = await session.execute(select(User).where(User.login == login_lower))
        if existing.scalar_one_or_none() is not None:
            raise AppError(f"Логин '{login_lower}' уже занят", status_code=400)

        password_hash = await hash_password(password)

        user = User(
            id=uuid.uuid4(),
            full_name=full_name or login_lower,
            login=login_lower,
            password_hash=password_hash,
        )
        session.add(user)
        await session.commit()

        return user


async def main():
    """Точка входа для CLI команд."""
    import argparse

    parser = argparse.ArgumentParser(description="LCT-7 CLI")
    subparsers = parser.add_subparsers(dest="command", help="Команда")

    create_parser = subparsers.add_parser("create-user", help="Создать пользователя")
    create_parser.add_argument("--login", required=True, help="Логин пользователя")
    create_parser.add_argument("--full-name", help="ФИО пользователя")
    create_parser.add_argument(
        "--password", help="Пароль пользователя (если не задан, будет запрос)"
    )

    args = parser.parse_args()

    if args.command == "create-user":
        settings = get_settings()

        password = args.password
        if password is None:
            password = getpass.getpass("Пароль: ")
            password_confirm = getpass.getpass("Подтверждение пароля: ")
            if password != password_confirm:
                print("Пароли не совпадают", file=sys.stderr)
                sys.exit(1)
        if not password:
            print("Пароль не может быть пустым", file=sys.stderr)
            sys.exit(1)

        try:
            engine = create_async_engine(settings.postgres.url)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            user = await create_user(
                session_factory,
                args.login,
                args.full_name,
                password,
            )

            print(f"Пользователь создан: {user.id} ({user.login})")
            await engine.dispose()
        except AppError as e:
            print(f"Ошибка: {e.message}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Ошибка: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
