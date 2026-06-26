"""OneDrive ingestion source — stub.

The full OneDrive implementation (Microsoft Graph OAuth, folder walk)
has been removed for this phase. Only ``file_upload`` and ``folder``
are exposed in the UI. The ``SourceType.ONEDRIVE`` enum value is
preserved so existing ``ingestion_run`` rows round-trip safely, but
the class is not registered and using it raises ``NotImplementedError``.

When OneDrive support is reinstated, restore the Graph-based
implementation and re-register it in ``ingestion_sources/__init__.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItem,
    IngestionItemContent,
    KBIngestionSource,
    SourceType,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


_DISABLED_MESSAGE = (
    "The OneDrive knowledge-base ingestion source is not available in this "
    "build. Use the file or folder upload paths instead."
)


class OneDriveSource(KBIngestionSource):
    """Stub kept for type-and-enum compatibility only."""

    source_type = SourceType.ONEDRIVE
    display_name = "OneDrive"
    description = "OneDrive ingestion is disabled in this build."
    icon = "onedrive"
    requires_credentials = True

    async def validate_config(self) -> None:
        raise NotImplementedError(_DISABLED_MESSAGE)

    async def list_items(self) -> AsyncIterator[IngestionItem]:  # type: ignore[override]
        raise NotImplementedError(_DISABLED_MESSAGE)
        if False:  # pragma: no cover — keeps this an async generator
            yield IngestionItem(item_id="", display_name="")

    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        raise NotImplementedError(_DISABLED_MESSAGE)
