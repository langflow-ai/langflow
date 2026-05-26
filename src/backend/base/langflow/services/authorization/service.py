"""Langflow authorization service (OSS pass-through; plugins enforce RBAC)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

from lfx.log.logger import logger
from lfx.services.authorization.base import BaseAuthorizationService
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.settings.auth import AuthSettings
    from lfx.services.settings.service import SettingsService


class LangflowAuthorizationService(BaseAuthorizationService):
    """OSS pass-through authorization service (always allows)."""

    def __init__(self, settings_service: SettingsService) -> None:
        """Store the settings service reference."""
        super().__init__()
        self.settings_service = settings_service
        self.set_ready()
        logger.debug("Langflow authorization service initialized")

    @property
    def name(self) -> str:
        """Return the canonical service-type name."""
        return ServiceType.AUTHORIZATION_SERVICE.value

    def _authz_settings(self) -> AuthSettings:
        """Return the live AuthSettings snapshot."""
        return self.settings_service.auth_settings

    async def is_enabled(self) -> bool:
        """Return True when AUTHZ_ENABLED is set."""
        return self._authz_settings().AUTHZ_ENABLED

    async def enforce(
        self,
        *,
        user_id: UUID,  # noqa: ARG002
        domain: str,  # noqa: ARG002
        obj: str,  # noqa: ARG002
        act: str,  # noqa: ARG002
        context: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> bool:
        """Allow every request in the OSS default."""
        return True

    async def batch_enforce(
        self,
        *,
        user_id: UUID,  # noqa: ARG002
        domain: str,  # noqa: ARG002
        requests: Sequence[tuple[str, str]],
        context: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> list[bool]:
        """Return True for each request."""
        return [True] * len(requests)
