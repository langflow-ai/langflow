"""Default authorization service for LFX (allows all; Langflow or plugins provide enforcement)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

from lfx.log.logger import logger
from lfx.services import register_service
from lfx.services.authorization.base import BaseAuthorizationService
from lfx.services.schema import ServiceType


@register_service(ServiceType.AUTHORIZATION_SERVICE)
class AuthorizationService(BaseAuthorizationService):
    """Default LFX authorization service that permits all actions."""

    def __init__(self) -> None:
        """Mark the no-op service as ready immediately (no external resources)."""
        super().__init__()
        self.set_ready()
        logger.debug("Authorization service initialized (no-op)")

    @property
    def name(self) -> str:
        """Return the canonical service-type name."""
        return ServiceType.AUTHORIZATION_SERVICE.value

    async def is_enabled(self) -> bool:
        """Always return False — the no-op service never enforces."""
        return False

    async def enforce(
        self,
        *,
        user_id: UUID,  # noqa: ARG002
        domain: str,  # noqa: ARG002
        obj: str,  # noqa: ARG002
        act: str,  # noqa: ARG002
        context: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> bool:
        """Always allow — the no-op default permits every request."""
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
