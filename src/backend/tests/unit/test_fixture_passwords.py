"""Only fixed fixture credentials may reuse hashes; custom authentication stays intact."""

from types import SimpleNamespace

from langflow.services.auth.service import AuthService
from lfx.services.settings.password_hashing import PasswordContext

from tests.fixture_passwords import FixturePasswords


def test_fixed_passwords_reuse_real_hashes_but_other_passwords_keep_fresh_salts():
    passwords = FixturePasswords()
    first = passwords.hash("testpassword")
    assert first.startswith("$2b$12$")
    assert passwords.hash("testpassword") == first
    assert PasswordContext.verify("testpassword", first)
    assert not PasswordContext.verify("wrong-password", first)
    assert passwords.hash("application-password") != passwords.hash("application-password")


def test_custom_auth_is_used_after_the_fixture_cache_is_warm():
    passwords = FixturePasswords()
    passwords.hash("testpassword")

    class CustomAuth(AuthService):
        def get_password_hash(self, password):
            return f"custom:{password}"

    auth = CustomAuth(SimpleNamespace())
    assert passwords.hasher(auth)("testpassword") == "custom:testpassword"


def test_replaced_password_context_is_used_after_the_fixture_cache_is_warm(monkeypatch):
    passwords = FixturePasswords()
    passwords.hash("testpassword")
    context = PasswordContext()
    auth = AuthService(SimpleNamespace(auth_settings=SimpleNamespace(pwd_context=context)))
    monkeypatch.setattr(context, "hash", lambda password: f"replacement:{password}")
    assert passwords.hasher(auth)("testpassword") == "replacement:testpassword"
