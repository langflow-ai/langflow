"""get_all_variables_for_provider(exclude=...) never reads the variables a caller is replacing.

Saving a new provider key validates it against the provider's other saved settings. The old key is
overwritten, so it must not be read: a value stored under another LANGFLOW_SECRET_KEY can't be
decrypted, and reading it blocked the save.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import pytest
from lfx.base.models.unified_models import credentials
from lfx.base.models.unified_models.credentials import get_all_variables_for_provider
from pydantic import SecretStr

USER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def saved_settings(monkeypatch):
    """Saved OpenAI settings whose key no longer decrypts; the base URL still reads."""

    @asynccontextmanager
    async def session_scope():
        yield object()

    async def read_variable(*, name, **_kwargs):
        if name == "OPENAI_API_KEY":
            msg = "Could not decrypt credential variable 'OPENAI_API_KEY'."
            raise ValueError(msg)
        return SecretStr("https://api.openai.com/v1")

    service = Mock(get_variable=AsyncMock(side_effect=read_variable))
    monkeypatch.setattr(credentials, "session_scope", session_scope)
    monkeypatch.setattr(credentials, "get_variable_service", lambda: service)
    return service


def _names_read(service: Mock) -> set[str]:
    return {call.kwargs["name"] for call in service.get_variable.await_args_list}


def test_reading_a_key_that_no_longer_decrypts_fails(saved_settings):
    with pytest.raises(ValueError, match="Could not decrypt"):
        get_all_variables_for_provider(USER_ID, "OpenAI")
    assert "OPENAI_API_KEY" in _names_read(saved_settings)


def test_an_excluded_key_is_never_read(saved_settings):
    result = get_all_variables_for_provider(USER_ID, "OpenAI", exclude=("OPENAI_API_KEY",))

    assert "OPENAI_API_KEY" not in _names_read(saved_settings)
    assert "OPENAI_API_KEY" not in result
    # The provider's other settings are still read, so the new key is checked against them.
    assert result.get("OPENAI_BASE_URL") == "https://api.openai.com/v1"


@pytest.mark.usefixtures("saved_settings")
def test_excluding_nothing_reads_every_setting():
    with pytest.raises(ValueError, match="Could not decrypt"):
        get_all_variables_for_provider(USER_ID, "OpenAI", exclude=())
