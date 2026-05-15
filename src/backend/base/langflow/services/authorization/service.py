"""Langflow authorization service (OSS default — fail-closed when enabled without enterprise plugin)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

from lfx.log.logger import logger
from lfx.services.authorization.base import BaseAuthorizationService
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class LangflowAuthorizationService(BaseAuthorizationService):
    """OSS authorization service.

    When ``AUTHZ_ENABLED`` is False (default), all requests are allowed.
    When True, only superusers pass (if ``AUTHZ_SUPERUSER_BYPASS``) until an enterprise
    plugin registers a Casbin-backed implementation via ``lfx.services`` entry points.
    """

    def __init__(self, settings_service: SettingsService) -> None:
        super().__init__()
        self.settings_service = settings_service
        self.set_ready()
        logger.debug("Langflow authorization service initialized")

    @property
    def name(self) -> str:
        return ServiceType.AUTHORIZATION_SERVICE.value

    def _authz_settings(self):
        return self.settings_service.auth_settings

    async def is_enabled(self) -> bool:
        return self._authz_settings().AUTHZ_ENABLED

    async def enforce(
        self,
        *,
        user_id: UUID,  # noqa: ARG002
        domain: str,  # noqa: ARG002
        obj: str,  # noqa: ARG002
        act: str,  # noqa: ARG002
        context: dict[str, Any] | None = None,
    ) -> bool:
        if not self._authz_settings().AUTHZ_ENABLED:
            return True

        ctx = context or {}
        return bool(
            self._authz_settings().AUTHZ_SUPERUSER_BYPASS and ctx.get("is_superuser"),
        )

    async def batch_enforce(
        self,
        *,
        user_id: UUID,
        domain: str,
        requests: Sequence[tuple[str, str]],
        context: dict[str, Any] | None = None,
    ) -> list[bool]:
        if not self._authz_settings().AUTHZ_ENABLED:
            return [True] * len(requests)

        allowed = await self.enforce(
            user_id=user_id,
            domain=domain,
            obj="*",
            act="*",
            context=context,
        )
        return [allowed] * len(requests)
