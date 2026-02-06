from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langflow.services.auth import utils as auth_utils
from langflow.services.base import Service
from langflow.services.schema import ServiceType
from lfx.services.manager import get_service_manager
from sqlmodel.ext.asyncio.session import AsyncSession


class DummyAuthService(Service):
    name = ServiceType.AUTH_SERVICE.value

    def __init__(self, settings_service=None):
        self.settings_service = settings_service or SimpleNamespace()
        self.calls: list[tuple[str, tuple]] = []
        self.set_ready()

    async def api_key_security(self, query_param, header_param):
        call = ("api_key_security", query_param, header_param)
        self.calls.append(call)
        return {"call": call}

    async def get_current_user(self, token, query_param, header_param, db):
        call = ("get_current_user", token, query_param, header_param)
        self.calls.append(call)
        return {"user": "dummy", "db": db}


@pytest.fixture
def dummy_auth_service():
    """A single DummyAuthService instance for patching."""
    return DummyAuthService()


@pytest.fixture
def dummy_auth_registration(dummy_auth_service):
    """Patch utils to return our DummyAuthService instance so delegation is tested."""
    service_manager = get_service_manager()
    try:
        _ = service_manager.get(ServiceType.SETTINGS_SERVICE)
        if not service_manager._plugins_discovered:
            service_manager.discover_plugins(None)
    except Exception:  # noqa: S110
        pass

    previous_class = service_manager.service_classes.get(ServiceType.AUTH_SERVICE)
    previous_instance = service_manager.services.pop(ServiceType.AUTH_SERVICE, None)
    service_manager.register_service_class(ServiceType.AUTH_SERVICE, DummyAuthService, override=True)

    try:
        with patch.object(auth_utils, "get_auth_service", return_value=dummy_auth_service):
            yield dummy_auth_service
    finally:
        service_manager.services.pop(ServiceType.AUTH_SERVICE, None)
        if previous_class is not None:
            service_manager.service_classes[ServiceType.AUTH_SERVICE] = previous_class
        else:
            service_manager.service_classes.pop(ServiceType.AUTH_SERVICE, None)
        if previous_instance is not None:
            service_manager.services[ServiceType.AUTH_SERVICE] = previous_instance


@pytest.mark.anyio
async def test_api_key_security_uses_registered_service(dummy_auth_registration):
    dummy = dummy_auth_registration
    sentinel = await auth_utils.api_key_security("query", "header")

    assert ("api_key_security", "query", "header") in dummy.calls
    assert sentinel["call"] == ("api_key_security", "query", "header")


@pytest.mark.anyio
async def test_get_current_user_delegates_to_service(dummy_auth_registration):
    dummy = dummy_auth_registration
    db = MagicMock(spec=AsyncSession)
    response = await auth_utils.get_current_user(token=None, query_param="q", header_param=None, db=db)

    assert ("get_current_user", None, "q", None) in dummy.calls
    assert response["user"] == "dummy"
    assert response["db"] is db
