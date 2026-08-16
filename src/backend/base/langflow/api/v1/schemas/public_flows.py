"""Pydantic schemas for the anonymous direct-link flow endpoint."""

from __future__ import annotations

from pydantic import Field

from langflow.services.authorization.public_access import PublicFlowCapabilities
from langflow.services.database.models.flow.model import FlowRead


class PublicFlowRead(FlowRead):
    """A direct-link flow payload plus the capabilities its visitor actually has.

    ``access_type`` alone cannot answer that question: a canonical
    ``AuthzShare(scope=public)`` admits a flow that is still PRIVATE, and the
    share's permission level — not the legacy flag — decides whether the visitor
    may run it. Clients gate on ``public_access`` so the UI matches the
    authorization decision that admitted the request.
    """

    public_access: PublicFlowCapabilities = Field(
        description="Anonymous actions permitted on this flow at its direct link.",
    )


__all__ = ["PublicFlowRead"]
