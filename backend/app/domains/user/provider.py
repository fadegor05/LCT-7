"""DI-провайдер домена user.

CurrentUser — единственное, что домен отдаёт наружу. Сейчас он разрешается в
стендового пользователя; когда появится авторизация, меняется только этот провайдер,
а потребители (`FromDishka[CurrentUser]`) остаются прежними.
"""

from typing import NewType

from dishka import Provider, Scope, provide

from app.domains.user.models import User
from app.domains.user.repository import UserRepository
from app.domains.user.service import UserService

CurrentUser = NewType("CurrentUser", User)


class UserProvider(Provider):
    scope = Scope.REQUEST

    repository = provide(UserRepository)
    service = provide(UserService)

    @provide
    async def current_user(self, service: UserService) -> CurrentUser:
        return CurrentUser(await service.get_current())
