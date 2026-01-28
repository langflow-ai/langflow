import asyncio
from uuid import uuid4

import langflow.services.database.models.api_key.crud as crud_module
import pytest
from cryptography.fernet import InvalidToken


class DummyResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class MockSession:
    def __init__(self, items):
        self._items = items

    async def exec(self, _query=None):
        # emulate SQLModel AsyncSession.exec returning a result with .all()
        await asyncio.sleep(0)  # ensure it's truly async
        return DummyResult(self._items)


class MockApiKeyObj:
    def __init__(self, data: dict):
        self._data = data

    def model_dump(self):
        return dict(self._data)


@pytest.mark.asyncio
async def test_get_api_keys_decrypts_and_falls_back(monkeypatch):
    user_id = uuid4()

    items = [
        MockApiKeyObj({"id": "1", "api_key": "enc-1", "name": "k1", "user_id": str(user_id)}),
        MockApiKeyObj({"id": "2", "api_key": "bad-enc", "name": "k2", "user_id": str(user_id)}),
        MockApiKeyObj({"id": "3", "api_key": None, "name": "k3", "user_id": str(user_id)}),
    ]

    session = MockSession(items)

    # Ensure get_settings_service returns a dummy settings (decrypt stub ignores it, but function expects it)
    monkeypatch.setattr(crud_module, "get_settings_service", lambda: object())

    monkeypatch.setattr(crud_module.auth_utils, "get_fernet", lambda _settings_service: None)

    # Patch decrypt_api_key to:
    # - return 'sk-decrypted' for 'enc-1'
    # - raise InvalidToken for 'bad-enc' to trigger fallback
    def fake_decrypt(val, *, settings_service=None, fernet_obj=None):  # noqa: ARG001
        if val == "enc-1":
            return "sk-decrypted"
        if val == "bad-enc":
            raise InvalidToken
        return val

    monkeypatch.setattr(crud_module.auth_utils, "decrypt_api_key", fake_decrypt)

    # Patch ApiKeyRead.model_validate to just return the provided dict for easy assertions
    monkeypatch.setattr(crud_module.ApiKeyRead, "model_validate", staticmethod(lambda data: data))

    result = await crud_module.get_api_keys(session, user_id)

    # three entries returned
    assert isinstance(result, list)
    assert len(result) == 3

    # first decrypted
    assert result[0]["api_key"] == "sk-decrypted"
    # second fell back to stored value 'bad-enc'
    assert result[1]["api_key"] == "bad-enc"
    # third remains None
    assert result[2]["api_key"] is None
