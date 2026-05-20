"""Langflow authorization service (OSS default — allows all; enterprise plugin enforces RBAC)."""

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
    """OSS authorization service (pass-through).

    ``ensure_*`` helpers still run when ``AUTHZ_ENABLED`` is True so routes stay wired,
    but this implementation always allows. Register an enterprise
    ``authorization_service`` (e.g. Casbin) via ``lfx.toml`` for real enforcement.
    """

    def __init__(self, settings_service: SettingsService) -> None:
        """Initialize the service with a reference to the live settings service."""
        super().__init__()
        self.settings_service = settings_service
        self.set_ready()
        logger.debug("Langflow authorization service initialized")

    @property
    def name(self) -> str:
        """Return the canonical service-type name."""
        return ServiceType.AUTHORIZATION_SERVICE.value

    def _authz_settings(self) -> AuthSettings:
        """Return the live AuthSettings snapshot from the settings service."""
        return self.settings_service.auth_settings

    async def is_enabled(self) -> bool:
        """Return True when AUTHZ_ENABLED is set in AuthSettings."""
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
        """Always allow — enterprise plugin overrides this for real enforcement."""
        return True

    async def batch_enforce(
        self,
        *,
        user_id: UUID,  # noqa: ARG002
        domain: str,  # noqa: ARG002
        requests: Sequence[tuple[str, str]],
        context: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> list[bool]:
        """Return a True list matching the request count."""
        return [True] * len(requests)
