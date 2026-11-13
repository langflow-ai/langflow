"""Reuse real bcrypt hashes only when arranging the API fixture's fixed users."""

from collections.abc import Callable

from langflow.services.auth.service import AuthService
from lfx.services.auth.base import BaseAuthService
from lfx.services.settings.password_hashing import PasswordContext

_PASSWORD_HASH = PasswordContext.hash
_AUTH_PASSWORD_HASH = AuthService.get_password_hash
_FIXTURE_PASSWORDS = frozenset({"testpassword", "test-superuser-password"})


class FixturePasswords:
    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}

    def hash(self, password: str) -> str:
        # Do not cache application credentials or change bcrypt's cost/salt format.
        if password not in _FIXTURE_PASSWORDS:
            return _PASSWORD_HASH(password)
        if password not in self._hashes:
            self._hashes[password] = _PASSWORD_HASH(password)
        return self._hashes[password]

    def hasher(self, auth: BaseAuthService) -> Callable[[str], str]:
        # Custom auth services and tests replacing the hash implementation must
        # still exercise their own implementation, even after the cache is warm.
        if type(auth) is AuthService and getattr(auth.get_password_hash, "__func__", None) is _AUTH_PASSWORD_HASH:
            context = auth.settings.auth_settings.pwd_context
            if type(context) is PasswordContext and context.hash is _PASSWORD_HASH:
                return self.hash
        return auth.get_password_hash
