"""Default auth service for LFX (no database/JWT; use Langflow auth for full auth)."""

from __future__ import annotations

from collections.abc import Coroutine
from typing import Any
from uuid import UUID

from lfx.log.logger import logger
from lfx.services import register_service
from lfx.services.auth.base import BaseAuthService
from lfx.services.schema import ServiceType


@register_service(ServiceType.AUTH_SERVICE)
class AuthService(BaseAuthService):
    """Default LFX auth service.

    No database, JWT, or API key validation. For full auth, configure
    auth_service = "langflow.services.auth.service:AuthService" in lfx.toml.
    """

    def __init__(self) -> None:
        """Initialize the auth service."""
        super().__init__()
        self.set_ready()
        logger.debug("Auth service initialized")

    @property
    def name(self) -> str:
        return ServiceType.AUTH_SERVICE.value

    async def authenticate_with_credentials(
        self,
        token: str | None,
        api_key: str | None,
        db: Any,
    ) -> Any:
        if not token and not api_key:
            raise NotImplementedError("No credentials provided")
        raise NotImplementedError("Authentication with credentials not implemented")

    async def get_current_user(
        self,
        token: str | Coroutine[Any, Any, str] | None,
        query_param: str | None,
        header_param: str | None,
        db: Any,
    ) -> Any:
        if not token and not query_param and not header_param:
            raise NotImplementedError("No credentials provided")
        raise NotImplementedError("get_current_user not implemented")

    async def get_current_user_for_websocket(
        self,
        token: str | None,
        api_key: str | None,
        db: Any,
    ) -> Any:
        raise NotImplementedError("WebSocket auth not implemented")

    async def get_current_user_for_sse(
        self,
        token: str | None,
        api_key: str | None,
        db: Any,
    ) -> Any:
        raise NotImplementedError("SSE auth not implemented")

    async def authenticate_user(
        self,
        username: str,
        password: str,
        db: Any,
    ) -> Any | None:
        logger.debug("Auth: authenticate_user (no-op)")
        return None

    async def get_current_active_user(self, current_user: Any) -> Any | None:
        """No user store; return None."""
        return None

    async def get_current_active_superuser(self, current_user: Any) -> Any | None:
        """No user store; return None."""
        return None

    async def create_user_tokens(
        self,
        user_id: UUID,
        db: Any,
        *,
        update_last_login: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError("create_user_tokens not implemented")

    async def create_refresh_token(self, refresh_token: str, db: Any) -> dict[str, Any]:
        raise NotImplementedError("create_refresh_token not implemented")

    async def api_key_security(
        self,
        query_param: str | None,
        header_param: str | None,
        db: Any | None = None,
    ) -> Any | None:
        return None

    async def ws_api_key_security(self, api_key: str | None) -> Any:
        raise NotImplementedError("ws_api_key_security not implemented")

    async def get_webhook_user(self, flow_id: str, request: Any) -> Any:
        raise NotImplementedError("get_webhook_user not implemented")

    async def create_super_user(self, username: str, password: str, db: Any) -> Any:
        raise NotImplementedError("create_super_user not implemented")

    async def create_user_longterm_token(self, db: Any) -> tuple[UUID, dict[str, Any]]:
        raise NotImplementedError("create_user_longterm_token not implemented")

    def create_user_api_key(self, user_id: UUID) -> dict[str, Any]:
        raise NotImplementedError("create_user_api_key not implemented")

    def encrypt_api_key(self, api_key: str) -> str:
        return api_key

    def decrypt_api_key(self, encrypted_api_key: str) -> str:
        return encrypted_api_key

    async def get_current_user_mcp(
        self,
        token: str | Coroutine[Any, Any, str] | None,
        query_param: str | None,
        header_param: str | None,
        db: Any,
    ) -> Any:
        raise NotImplementedError("get_current_user_mcp not implemented")

    def get_or_create_super_user(self, current_user: Any) -> Any:
        """No user store; raise."""
        raise NotImplementedError("get_or_create_super_user not implemented")

    async def get_current_user_from_access_token(
        self,
        token: str | Coroutine[Any, Any, str] | None,
        db: Any,
    ) -> Any:
        if not token:
            raise NotImplementedError("No token provided")
        raise NotImplementedError("Token validation not implemented")

    def create_token(self, data: dict[str, Any], expires_delta: Any) -> str:
        raise NotImplementedError("create_token not implemented")

    def get_user_id_from_token(self, token: str) -> UUID:
        raise NotImplementedError("get_user_id_from_token not implemented")

    async def teardown(self) -> None:
        logger.debug("Auth service teardown")
