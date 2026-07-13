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
        # Loud, operator-visible warning when AUTHZ_ENABLED is on but the
        # registered service is the OSS pass-through. Without an enforcement
        # plugin registered via ``lfx.toml``, ``enforce()`` returns True for
        # every request — so flipping the env var alone changes nothing except
        # audit-log emission. The dry-run CLI helps verify policy decisions,
        # but ops engineers can be misled by a "True" flag.
        try:
            authz_enabled = bool(getattr(settings_service.auth_settings, "AUTHZ_ENABLED", False))
        except Exception:  # noqa: BLE001 — never break startup on a warning probe
            authz_enabled = False
        if authz_enabled and not self.SUPPORTS_CROSS_USER_FETCH:
            logger.warning(
                "LANGFLOW_AUTHZ_ENABLED=true but the OSS pass-through authorization service is "
                "registered (no enforcement plugin found). Every enforce() call will return True; "
                "route guards still run and audit rows still write, but no policy is applied. "
                "Register an authorization plugin via lfx.toml or set LANGFLOW_AUTHZ_ENABLED=false "
                "to silence this warning."
            )

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
