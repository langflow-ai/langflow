"""Microsoft Graph OAuth source helper — stub.

The full Microsoft-Graph OAuth helper (refresh-token rotation, shared
HTTP client, file fetch) has been removed for this phase along with the
OneDrive and SharePoint connectors that built on top of it. The class
is kept as a stub so the public symbol re-exported from
``ingestion_sources/__init__.py`` keeps importing.

When OneDrive / SharePoint support is reinstated, restore the full
implementation and re-add the concrete connectors in
``ingestion_sources/__init__.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItem,
    IngestionItemContent,
)
from lfx.base.knowledge_bases.ingestion_sources.connector_base import OAuthConnectorBase

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


_DISABLED_MESSAGE = "Microsoft Graph (OneDrive / SharePoint) ingestion sources are not available in this build."


class MicrosoftGraphSource(OAuthConnectorBase):
    """Stub kept for import-compat only.

    Concrete subclasses (``OneDriveSource``, ``SharePointSource``) are
    themselves stubs that no longer inherit from this class while
    Microsoft Graph support is disabled. This class exists only so
    callers importing ``MicrosoftGraphSource`` from the package keep
    working.
    """

    display_name = "Microsoft Graph"
    description = _DISABLED_MESSAGE
    requires_credentials = True

    async def validate_config(self) -> None:
        raise NotImplementedError(_DISABLED_MESSAGE)

    async def list_items(self) -> AsyncIterator[IngestionItem]:  # type: ignore[override]
        raise NotImplementedError(_DISABLED_MESSAGE)
        if False:  # pragma: no cover — keeps this an async generator
            yield IngestionItem(item_id="", display_name="")

    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        raise NotImplementedError(_DISABLED_MESSAGE)
