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

    async def get_current_user(self, token, query_param, header_param, db, external_token=None):
        call = ("get_current_user", token, query_param, header_param, external_token)
        self.calls.append(call)
        return {"user": "dummy", "db": db}

    async def get_current_user_mcp(self, token, query_param, header_param, db, external_token=None):
        call = ("get_current_user_mcp", token, query_param, header_param, external_token)
        self.calls.append(call)
        return {"user": "dummy-mcp", "db": db}


class LegacyDummyAuthService(DummyAuthService):
    async def get_current_user_mcp(self, token, query_param, header_param, db):
        call = ("get_current_user_mcp", token, query_param, header_param)
        self.calls.append(call)
        return {"user": "legacy-mcp", "db": db}


class BrokenDummyAuthService(DummyAuthService):
    async def get_current_user_mcp(self, token, query_param, header_param, db, external_token=None):  # noqa: ARG002
        msg = "service implementation failed"
        raise TypeError(msg)


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
    # get_current_user now extracts the external credential from the request and
    # threads it to the service as external_token. With external auth disabled the
    # extractor returns None, so delegation records external_token=None.
    request = SimpleNamespace(headers={}, cookies={})
    response = await auth_utils.get_current_user(request, token=None, query_param="q", header_param=None, db=db)

    assert ("get_current_user", None, "q", None, None) in dummy.calls
    assert response["user"] == "dummy"
    assert response["db"] is db


@pytest.mark.anyio
async def test_get_current_user_mcp_delegates_external_credential(dummy_auth_registration):
    dummy = dummy_auth_registration
    db = MagicMock(spec=AsyncSession)
    request = SimpleNamespace(headers={}, cookies={})

    with patch.object(auth_utils, "_get_external_token", return_value="external-mcp-credential"):
        response = await auth_utils.get_current_user_mcp(
            request, token=None, query_param=None, header_param=None, db=db
        )

    assert ("get_current_user_mcp", None, None, None, "external-mcp-credential") in dummy.calls
    assert response["user"] == "dummy-mcp"
    assert response["db"] is db


@pytest.mark.anyio
async def test_get_current_user_mcp_supports_legacy_signature_with_external_auth_disabled():
    service = LegacyDummyAuthService()
    db = MagicMock(spec=AsyncSession)
    request = SimpleNamespace(headers={}, cookies={})

    with (
        patch.object(auth_utils, "_auth_service", return_value=service),
        patch.object(auth_utils, "_get_external_token", return_value=None),
    ):
        response = await auth_utils.get_current_user_mcp(
            request, token=None, query_param="legacy-query-key", header_param=None, db=db
        )

    assert ("get_current_user_mcp", None, "legacy-query-key", None) in service.calls
    assert response["user"] == "legacy-mcp"
    assert response["db"] is db


@pytest.mark.anyio
async def test_get_current_user_mcp_supports_legacy_signature_with_external_auth_enabled():
    service = LegacyDummyAuthService()
    db = MagicMock(spec=AsyncSession)
    request = SimpleNamespace(headers={}, cookies={})
    native_token = "legacy-native-token"  # noqa: S105  # pragma: allowlist secret

    with (
        patch.object(auth_utils, "_auth_service", return_value=service),
        patch.object(auth_utils, "_get_external_token", return_value="external-mcp-credential"),
    ):
        response = await auth_utils.get_current_user_mcp(
            request, token=native_token, query_param=None, header_param="legacy-header-key", db=db
        )

    assert ("get_current_user_mcp", native_token, None, "legacy-header-key") in service.calls
    assert response["user"] == "legacy-mcp"
    assert response["db"] is db


@pytest.mark.anyio
async def test_get_current_user_mcp_does_not_mask_service_type_errors():
    service = BrokenDummyAuthService()
    request = SimpleNamespace(headers={}, cookies={})

    with (
        patch.object(auth_utils, "_auth_service", return_value=service),
        patch.object(auth_utils, "_get_external_token", return_value="external-mcp-credential"),
        pytest.raises(TypeError, match="service implementation failed"),
    ):
        await auth_utils.get_current_user_mcp(
            request, token=None, query_param=None, header_param=None, db=MagicMock(spec=AsyncSession)
        )


@pytest.mark.anyio
async def test_lfx_no_op_mcp_signature_accepts_external_credential():
    from lfx.services.auth.service import AuthService as LFXNoOpAuthService

    service = LFXNoOpAuthService()
    with pytest.raises(NotImplementedError, match="get_current_user_mcp not implemented"):
        await service.get_current_user_mcp(
            None,
            None,
            None,
            MagicMock(),
            external_token="external-mcp-credential",  # noqa: S106
        )


def test_get_auth_service_replaces_lfx_no_op_stub():
    """LFX's no-op auth service must never be what Langflow resolves.

    It self-registers for the ``auth_service`` slot at import time, so any process that
    touches auth before ``register_all_service_factories()`` would otherwise get a service
    that raises ``NotImplementedError`` for user/token operations and answers API-key
    checks with ``None``.
    """
    from langflow.services.auth.service import AuthService as LangflowAuthService
    from langflow.services.deps import get_auth_service
    from lfx.services.auth.service import AuthService as LFXNoOpAuthService

    service_manager = get_service_manager()
    previous_class = service_manager.service_classes.get(ServiceType.AUTH_SERVICE)
    previous_instance = service_manager.services.pop(ServiceType.AUTH_SERVICE, None)
    service_manager.register_service_class(ServiceType.AUTH_SERVICE, LFXNoOpAuthService, override=True)

    try:
        assert isinstance(service_manager.get(ServiceType.AUTH_SERVICE), LFXNoOpAuthService)
        assert isinstance(get_auth_service(), LangflowAuthService)
    finally:
        service_manager.services.pop(ServiceType.AUTH_SERVICE, None)
        if previous_class is not None:
            service_manager.service_classes[ServiceType.AUTH_SERVICE] = previous_class
        else:
            service_manager.service_classes.pop(ServiceType.AUTH_SERVICE, None)
        if previous_instance is not None:
            service_manager.services[ServiceType.AUTH_SERVICE] = previous_instance
