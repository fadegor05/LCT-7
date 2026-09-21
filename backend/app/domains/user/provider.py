"""DI-провайдер домена user (аналог UserModule.kt / Koin-модуля).

Dishka сам подставит зависимости в конструкторы: UserRepository(session),
UserService(repository, session). Оба — в scope REQUEST, живут ровно один запрос.
"""

from dishka import Provider, Scope, provide

from app.domains.user.repository import UserRepository
from app.domains.user.service import UserService


class UserProvider(Provider):
    scope = Scope.REQUEST

    repository = provide(UserRepository)
    service = provide(UserService)
