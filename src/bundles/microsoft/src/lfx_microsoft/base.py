"""Shared base for every Microsoft Graph action component.

Each component declares one manifest capability. The base turns that into a
credential lease, pre-flights the conditional scopes the resolver cannot see,
and wraps the provider call in the integration telemetry boundary.

This module is also the bundle's import facade for the ``lfx`` field types.
``lfx.custom.custom_component.component`` must be imported before ``lfx.io``
or ``lfx.inputs`` -- importing the field types first leaves the component
module half-initialized (a cold ``import lfx.io`` followed by
``from lfx.custom.custom_component.component import Component`` raises
``ImportError`` on lfx 1.13). Re-exporting the field types here means every
component module has exactly one lfx-facing import and cannot get that order
wrong.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, ClassVar

from lfx.custom.custom_component.component import Component
from lfx.integrations.capabilities import ScopeSet
from lfx.integrations.errors import ScopeMissingError
from lfx.integrations.telemetry import integration_action
from lfx.io import (
    BoolInput,
    DataInput,
    DropdownInput,
    FileInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
)
from lfx.schema.data import Data
from lfx.schema.message import Message

from lfx_microsoft.graph import PROVIDER_ID, GraphClient
from lfx_microsoft.manifest import capability

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lfx.integrations.models import CredentialLease, ResolvedCredential

__all__ = [
    "BoolInput",
    "Data",
    "DataInput",
    "DropdownInput",
    "FileInput",
    "IntInput",
    "Message",
    "MessageTextInput",
    "MicrosoftGraphComponent",
    "MultilineInput",
    "Output",
    "as_dict_list",
    "as_list",
    "recipients",
]


class MicrosoftGraphComponent(Component):
    """Base class for the delegated Microsoft Graph actions."""

    icon = "Microsoft"
    capability_id: ClassVar[str] = ""

    # Test seam: an ``httpx.AsyncBaseTransport`` used instead of the network.
    graph_transport: Any = None
    graph_base_url: str | None = None

    def lease(self) -> CredentialLease:
        """Return the credential lease for the declared connection field."""
        return self.resolve_connection("connection")

    def client(self, lease: CredentialLease) -> GraphClient:
        """Build a Graph client bound to ``lease``."""
        kwargs: dict[str, Any] = {}
        if self.graph_transport is not None:
            kwargs["transport"] = self.graph_transport
        if self.graph_base_url:
            kwargs["base_url"] = self.graph_base_url
        return GraphClient(lease, **kwargs)

    def _preflight_scopes(self, credential: ResolvedCredential, inputs: dict[str, Any]) -> None:
        """Fail before the network call when a conditional scope is missing.

        ``Component.resolve_connection`` only forwards ``required_scopes``, so
        conditional requirements such as ``Files.Read.All`` (active only when a
        drive id is supplied) would otherwise surface as an opaque Graph 403.
        A credential whose scopes were never verified is left to the provider.
        """
        if not credential.scopes_verified:
            return
        missing = ScopeSet.covers(
            capability(self.capability_id),
            inputs,
            credential.granted_scopes,
            provider=PROVIDER_ID,
        )
        if missing:
            raise ScopeMissingError(missing, provider=PROVIDER_ID)

    @asynccontextmanager
    async def action(self, lease: CredentialLease, inputs: dict[str, Any] | None = None) -> AsyncIterator[GraphClient]:
        """Resolve, pre-flight, measure and normalize one Graph action."""
        credential = await lease.get_credential()
        self._preflight_scopes(credential, inputs or {})
        client = self.client(lease)
        try:
            async with integration_action(
                self,
                provider=PROVIDER_ID,
                capability=self.capability_id,
                owner_kind=credential.owner_kind,
            ):
                yield client
        finally:
            await client.aclose()


def as_list(value: Any) -> list[str]:
    """Normalize a possibly-scalar, possibly-comma-separated input into a list."""
    if value is None:
        return []
    if isinstance(value, str):
        items = [entry.strip() for entry in value.replace(";", ",").split(",")]
    elif isinstance(value, (list, tuple, set)):
        items = [str(entry).strip() for entry in value]
    else:
        items = [str(value).strip()]
    return [item for item in items if item]


def as_dict_list(value: Any) -> list[dict[str, Any]]:
    """Normalize a Data / dict / list input into a list of plain dictionaries."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    normalized: list[dict[str, Any]] = []
    for item in items:
        data = getattr(item, "data", None)
        if isinstance(data, dict):
            normalized.append(dict(data))
        elif isinstance(item, dict):
            normalized.append(item)
    return normalized


def recipients(addresses: Any) -> list[dict[str, dict[str, str]]]:
    """Build a Graph ``emailAddress`` recipient list."""
    return [{"emailAddress": {"address": address}} for address in as_list(addresses)]
